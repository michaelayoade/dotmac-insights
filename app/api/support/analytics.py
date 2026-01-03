"""Support analytics and insights endpoints.

Thin wrappers around SupportAnalyticsService.
All business logic resides in the service layer.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require, get_current_user, Principal
from app.cache import cached, CACHE_TTL
from app.services.support import (
    SupportAnalyticsService,
    AnalyticsFilters,
)

router = APIRouter()


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

def get_analytics_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_user),
) -> SupportAnalyticsService:
    """Provide SupportAnalyticsService instance for dependency injection."""
    return SupportAnalyticsService(db, principal)


def _build_filters(
    days: int = 30,
    team_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    channel: Optional[str] = None,
    priority: Optional[str] = None,
    ticket_type: Optional[str] = None,
) -> AnalyticsFilters:
    """Build AnalyticsFilters from query parameters."""
    return AnalyticsFilters(
        days=days,
        team_id=team_id,
        agent_id=agent_id,
        channel=channel,
        priority=priority,
        ticket_type=ticket_type,
    )


# =============================================================================
# OVERVIEW & DASHBOARD
# =============================================================================

@router.get("/analytics/overview", dependencies=[Depends(Require("analytics:read"))])
def get_support_overview(
    days: int = Query(default=30, le=365),
    team_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    channel: Optional[str] = None,
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get high-level support overview statistics."""
    filters = _build_filters(days=days, team_id=team_id, agent_id=agent_id, channel=channel)
    stats = service.get_overview(filters)
    return {
        "ticket_volume": {
            "total": stats.total_tickets,
            "open": stats.open_tickets,
            "resolved": stats.resolved_tickets,
            "closed": stats.closed_tickets,
            "pending": stats.pending_tickets,
        },
        "resolution_time": {
            "avg_hours": stats.avg_resolution_hours,
        },
        "first_response_time": {
            "avg_hours": stats.avg_first_response_hours,
        },
        "sla": {
            "attainment_rate": stats.sla_attainment_pct,
        },
        "csat": {
            "score": stats.csat_score,
        },
        "period_days": stats.period_days,
    }


@router.get("/metrics", dependencies=[Depends(Require("analytics:read"))])
def get_support_metrics(
    days: int = Query(default=30, le=90),
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Simplified metrics endpoint for dashboards."""
    filters = _build_filters(days=days)
    stats = service.get_overview(filters)
    return {
        "period_days": stats.period_days,
        "total": stats.total_tickets,
        "resolved": stats.resolved_tickets + stats.closed_tickets,
        "open": stats.open_tickets,
        "avg_resolution_hours": stats.avg_resolution_hours,
        "avg_first_response_hours": stats.avg_first_response_hours,
        "sla_attainment_pct": stats.sla_attainment_pct,
    }


# =============================================================================
# VOLUME TRENDS
# =============================================================================

@router.get("/analytics/volume-trend", dependencies=[Depends(Require("analytics:read"))])
def get_volume_trend(
    days: int = Query(default=90, le=365),
    granularity: str = Query(default="month", regex="^(day|week|month)$"),
    team_id: Optional[int] = None,
    channel: Optional[str] = None,
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get ticket volume trend over time."""
    filters = _build_filters(days=days, team_id=team_id, channel=channel)
    trend = service.get_volume_trend(filters, granularity=granularity)
    return {
        "data": [
            {
                "period": p.period,
                "year": p.year,
                "month": p.month,
                "day": p.day,
                "total": p.total,
                "opened": p.opened,
                "resolved": p.resolved,
                "closed": p.closed,
                "resolution_rate": round((p.resolved + p.closed) / p.total * 100, 1) if p.total > 0 else 0,
            }
            for p in trend.data
        ],
        "summary": {
            "total_opened": trend.total_opened,
            "total_resolved": trend.total_resolved,
            "avg_daily_volume": trend.avg_daily_volume,
            "peak_day": trend.peak_day,
            "peak_volume": trend.peak_volume,
        },
    }


# =============================================================================
# RESOLUTION & RESPONSE TIME
# =============================================================================

@router.get("/analytics/resolution-time", dependencies=[Depends(Require("analytics:read"))])
def get_resolution_time_stats(
    days: int = Query(default=30, le=365),
    team_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    priority: Optional[str] = None,
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get resolution time statistics."""
    filters = _build_filters(days=days, team_id=team_id, agent_id=agent_id, priority=priority)
    stats = service.get_resolution_stats(filters)
    return {
        "avg_hours": stats.avg_hours,
        "median_hours": stats.median_hours,
        "p90_hours": stats.p90_hours,
        "p95_hours": stats.p95_hours,
        "min_hours": stats.min_hours,
        "max_hours": stats.max_hours,
        "sample_size": stats.sample_size,
    }


@router.get("/analytics/first-response", dependencies=[Depends(Require("analytics:read"))])
def get_first_response_stats(
    days: int = Query(default=30, le=365),
    team_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    channel: Optional[str] = None,
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get first response time statistics."""
    filters = _build_filters(days=days, team_id=team_id, agent_id=agent_id, channel=channel)
    stats = service.get_first_response_stats(filters)
    return {
        "avg_hours": stats.avg_hours,
        "median_hours": stats.median_hours,
        "p90_hours": stats.p90_hours,
        "within_sla_pct": stats.within_sla_pct,
        "sample_size": stats.sample_size,
    }


# =============================================================================
# CATEGORY & CHANNEL BREAKDOWN
# =============================================================================

@router.get("/analytics/by-category", dependencies=[Depends(Require("analytics:read"))])
def get_tickets_by_category(
    days: int = Query(default=30, le=90),
    category_field: str = Query(default="ticket_type", regex="^(ticket_type|issue_type|priority)$"),
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get ticket distribution by category."""
    filters = _build_filters(days=days)
    stats = service.get_category_breakdown(filters, category_field=category_field)
    return {
        "category_field": category_field,
        "data": [
            {
                "category": s.category,
                "count": s.total_tickets,
                "resolved": s.resolved_tickets,
                "resolution_rate": s.resolution_rate,
                "avg_resolution_hours": s.avg_resolution_hours,
                "pct_of_total": s.pct_of_total,
            }
            for s in stats
        ],
    }


@router.get("/analytics/by-channel", dependencies=[Depends(Require("analytics:read"))])
def get_tickets_by_channel(
    days: int = Query(default=30, le=90),
    team_id: Optional[int] = None,
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get ticket distribution by support channel."""
    filters = _build_filters(days=days, team_id=team_id)
    stats = service.get_channel_breakdown(filters)
    return {
        "data": [
            {
                "channel": s.channel,
                "count": s.total_tickets,
                "resolved": s.resolved_tickets,
                "resolution_rate": s.resolution_rate,
                "avg_resolution_hours": s.avg_resolution_hours,
                "avg_first_response_hours": s.avg_first_response_hours,
                "sla_attainment_pct": s.sla_attainment_pct,
                "pct_of_total": s.pct_of_total,
            }
            for s in stats
        ],
    }


# =============================================================================
# SLA PERFORMANCE
# =============================================================================

@router.get("/analytics/sla-performance", dependencies=[Depends(Require("analytics:read"))])
@cached("support-sla", ttl=CACHE_TTL["medium"])
async def get_sla_performance(
    days: int = Query(default=90, le=365),
    team_id: Optional[int] = None,
    priority: Optional[str] = None,
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> List[Dict[str, Any]]:
    """Get SLA attainment trend by month."""
    filters = _build_filters(days=days, team_id=team_id, priority=priority)
    stats = service.get_sla_performance(filters)
    return [
        {
            "period": s.period,
            "response": {
                "met": s.response_met,
                "breached": s.response_breached,
                "attainment_pct": s.response_attainment_pct,
            },
            "resolution": {
                "met": s.resolution_met,
                "breached": s.resolution_breached,
                "attainment_pct": s.resolution_attainment_pct,
            },
            "total_tracked": s.total_tracked,
        }
        for s in stats
    ]


# =============================================================================
# AGENT PERFORMANCE
# =============================================================================

@router.get("/insights/agent-performance", dependencies=[Depends(Require("analytics:read"))])
@cached("support-agent-perf", ttl=CACHE_TTL["medium"])
async def get_agent_performance(
    days: int = Query(default=30, le=90),
    team_id: Optional[int] = None,
    limit: int = Query(default=50, le=100),
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get agent performance metrics."""
    filters = _build_filters(days=days, team_id=team_id)
    agents = service.get_agent_performance(filters, limit=limit)
    return {
        "agents": [
            {
                "agent_id": a.agent_id,
                "agent_name": a.agent_name,
                "team_id": a.team_id,
                "team_name": a.team_name,
                "total_tickets": a.total_tickets,
                "resolved_tickets": a.resolved_tickets,
                "resolution_rate": a.resolution_rate,
                "avg_resolution_hours": a.avg_resolution_hours,
                "avg_first_response_hours": a.avg_first_response_hours,
                "sla_attainment_pct": a.sla_attainment_pct,
                "csat_score": a.csat_score,
                "csat_responses": a.csat_responses,
                "current_open": a.current_open,
                "capacity": a.capacity,
                "utilization_pct": a.utilization_pct,
            }
            for a in agents
        ],
        "count": len(agents),
    }


# =============================================================================
# TEAM PERFORMANCE
# =============================================================================

@router.get("/insights/team-performance", dependencies=[Depends(Require("analytics:read"))])
@cached("support-team-perf", ttl=CACHE_TTL["medium"])
async def get_team_performance(
    days: int = Query(default=30, le=90),
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get team performance metrics."""
    filters = _build_filters(days=days)
    teams = service.get_team_performance(filters)
    return {
        "teams": [
            {
                "team_id": t.team_id,
                "team_name": t.team_name,
                "total_agents": t.total_agents,
                "active_agents": t.active_agents,
                "total_tickets": t.total_tickets,
                "resolved_tickets": t.resolved_tickets,
                "resolution_rate": t.resolution_rate,
                "avg_resolution_hours": t.avg_resolution_hours,
                "avg_first_response_hours": t.avg_first_response_hours,
                "sla_attainment_pct": t.sla_attainment_pct,
                "csat_score": t.csat_score,
                "current_open": t.current_open,
                "total_capacity": t.total_capacity,
                "utilization_pct": t.utilization_pct,
                "top_performers": t.top_performers,
            }
            for t in teams
        ],
        "count": len(teams),
    }


# =============================================================================
# BACKLOG AGING
# =============================================================================

@router.get("/insights/backlog-aging", dependencies=[Depends(Require("analytics:read"))])
def get_backlog_aging(
    team_id: Optional[int] = None,
    priority: Optional[str] = None,
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Analyze open ticket backlog by age."""
    filters = _build_filters(team_id=team_id, priority=priority)
    aging = service.get_backlog_aging(filters)
    return {
        "buckets": [
            {
                "age_bucket": a.age_bucket,
                "count": a.count,
                "pct_of_backlog": a.pct_of_backlog,
                "avg_priority": a.avg_priority,
                "sla_at_risk": a.sla_at_risk,
            }
            for a in aging
        ],
        "total_backlog": sum(a.count for a in aging),
    }


# =============================================================================
# REOPEN ANALYSIS
# =============================================================================

@router.get("/insights/reopen-analysis", dependencies=[Depends(Require("analytics:read"))])
def get_reopen_analysis(
    days: int = Query(default=30, le=90),
    team_id: Optional[int] = None,
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Analyze ticket reopens and rework."""
    filters = _build_filters(days=days, team_id=team_id)
    analysis = service.get_reopen_analysis(filters)
    return {
        "total_reopened": analysis.total_reopened,
        "reopen_rate": analysis.reopen_rate,
        "avg_reopens_per_ticket": analysis.avg_reopens_per_ticket,
        "top_reopen_reasons": analysis.top_reopen_reasons,
        "by_agent": analysis.by_agent,
        "by_category": analysis.by_category,
    }


# =============================================================================
# PATTERN INSIGHTS
# =============================================================================

@router.get("/insights/patterns", dependencies=[Depends(Require("analytics:read"))])
@cached("support-patterns", ttl=CACHE_TTL["medium"])
async def get_support_patterns(
    days: int = Query(default=30, le=90),
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Analyze support patterns including peak times and common issues."""
    filters = _build_filters(days=days)
    patterns = service.get_pattern_insights(filters)
    return {
        "peak_hours": patterns.peak_hours,
        "peak_days": patterns.peak_days,
        "busiest_period": patterns.busiest_period,
        "quietest_period": patterns.quietest_period,
        "by_region": patterns.by_region,
        "seasonal_factors": patterns.seasonal_factors,
    }


# =============================================================================
# AUTOMATION EFFECTIVENESS
# =============================================================================

@router.get("/insights/automation", dependencies=[Depends(Require("analytics:read"))])
def get_automation_effectiveness(
    days: int = Query(default=30, le=90),
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Analyze automation rule effectiveness."""
    filters = _build_filters(days=days)
    effectiveness = service.get_automation_effectiveness(filters)
    return {
        "total_executions": effectiveness.total_executions,
        "successful_executions": effectiveness.successful_executions,
        "success_rate": effectiveness.success_rate,
        "tickets_auto_assigned": effectiveness.tickets_auto_assigned,
        "tickets_auto_categorized": effectiveness.tickets_auto_categorized,
        "tickets_auto_responded": effectiveness.tickets_auto_responded,
        "avg_time_saved_hours": effectiveness.avg_time_saved_hours,
        "top_rules": effectiveness.top_rules,
    }


# =============================================================================
# KB DEFLECTION
# =============================================================================

@router.get("/insights/kb-deflection", dependencies=[Depends(Require("analytics:read"))])
def get_kb_deflection(
    days: int = Query(default=30, le=90),
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Analyze knowledge base article effectiveness and deflection."""
    filters = _build_filters(days=days)
    deflection = service.get_kb_deflection(filters)
    return {
        "total_article_views": deflection.total_article_views,
        "helpful_votes": deflection.helpful_votes,
        "not_helpful_votes": deflection.not_helpful_votes,
        "helpfulness_rate": deflection.helpfulness_rate,
        "estimated_deflections": deflection.estimated_deflections,
        "deflection_rate": deflection.deflection_rate,
        "top_articles": deflection.top_articles,
        "search_no_results": deflection.search_no_results,
    }


# =============================================================================
# END-TO-END REPORT
# =============================================================================

@router.get("/reports/e2e", dependencies=[Depends(Require("analytics:read"))])
def get_e2e_report(
    days: int = Query(default=30, le=365),
    team_id: Optional[int] = None,
    channel: Optional[str] = None,
    service: SupportAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Generate a comprehensive end-to-end support report."""
    filters = _build_filters(days=days, team_id=team_id, channel=channel)
    report = service.generate_e2e_report(filters)

    # Convert dataclasses to dicts for JSON serialization
    return {
        "report_period": report.report_period,
        "generated_at": report.generated_at.isoformat(),
        "overview": asdict(report.overview),
        "volume_trend": {
            "data": [asdict(p) for p in report.volume_trend.data],
            "total_opened": report.volume_trend.total_opened,
            "total_resolved": report.volume_trend.total_resolved,
            "avg_daily_volume": report.volume_trend.avg_daily_volume,
            "peak_day": report.volume_trend.peak_day,
            "peak_volume": report.volume_trend.peak_volume,
        },
        "resolution_stats": asdict(report.resolution_stats),
        "first_response_stats": asdict(report.first_response_stats),
        "sla_performance": [asdict(s) for s in report.sla_performance],
        "agent_performance": [asdict(a) for a in report.agent_performance],
        "team_performance": [asdict(t) for t in report.team_performance],
        "channel_breakdown": [asdict(c) for c in report.channel_breakdown],
        "category_breakdown": [asdict(c) for c in report.category_breakdown],
        "backlog_aging": [asdict(b) for b in report.backlog_aging],
        "reopen_analysis": asdict(report.reopen_analysis),
        "patterns": asdict(report.patterns),
        "automation": asdict(report.automation),
        "kb_deflection": asdict(report.kb_deflection),
    }
