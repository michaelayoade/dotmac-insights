"""
Performance Analytics API - Dashboards and reporting
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.performance import (
    EvaluationPeriod,
    EmployeeScorecardInstance,
    ScorecardInstanceStatus,
    KRAResult,
    KPIResult,
    KRADefinition,
    PerformanceSnapshot,
    BonusPolicy,
)
from app.models.employee import Employee
from app.models.hr import Department
from app.services.performance_service import PerformanceService

router = APIRouter(prefix="/analytics", tags=["performance-analytics"])


# ============= SCHEMAS =============
class DashboardSummary(BaseModel):
    active_period: Optional[dict] = None
    total_employees: int = 0
    scorecards_generated: int = 0
    scorecards_computed: int = 0
    scorecards_in_review: int = 0
    scorecards_finalized: int = 0
    avg_score: Optional[float] = None
    score_distribution: dict = {}
    top_performers: List[dict] = []
    improvement_needed: List[dict] = []


class TeamPerformance(BaseModel):
    department: str
    employee_count: int
    avg_score: Optional[float]
    min_score: Optional[float]
    max_score: Optional[float]
    finalized_count: int


class ScoreTrend(BaseModel):
    period_code: str
    period_name: str
    avg_score: Optional[float]
    employee_count: int


class ScoreDistribution(BaseModel):
    rating: str
    min_score: float
    max_score: float
    count: int
    percentage: float


class BonusEligibility(BaseModel):
    employee_id: int
    employee_name: str
    department: Optional[str]
    final_score: Optional[float]
    rating: Optional[str]
    bonus_factor: Optional[float]
    bonus_band: Optional[str]


# ============= ENDPOINTS =============
@router.get("/dashboard", response_model=DashboardSummary, dependencies=[Depends(Require("performance:read"))])
async def get_dashboard(
    period_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get executive dashboard summary."""
    # Get active or specified period
    if period_id:
        period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
    else:
        period = db.query(EvaluationPeriod).filter(
            EvaluationPeriod.status.in_(['active', 'scoring', 'review'])
        ).order_by(EvaluationPeriod.start_date.desc()).first()

    if not period:
        return DashboardSummary()

    period_id = period.id

    # Counts
    total_employees = db.query(func.count(Employee.id)).filter(Employee.status == 'Active').scalar() or 0

    base_query = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id
    )

    scorecards_generated = base_query.count()

    scorecards_computed = base_query.filter(
        EmployeeScorecardInstance.status.in_(['computed', 'in_review', 'approved', 'finalized'])
    ).count()

    scorecards_in_review = base_query.filter(
        EmployeeScorecardInstance.status.in_(['computed', 'in_review'])
    ).count()

    scorecards_finalized = base_query.filter(
        EmployeeScorecardInstance.status == 'finalized'
    ).count()

    # Average score
    avg_score_result = db.query(func.avg(EmployeeScorecardInstance.total_weighted_score)).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id,
        EmployeeScorecardInstance.total_weighted_score.isnot(None)
    ).scalar()
    avg_score = float(avg_score_result) if avg_score_result is not None else None

    # Score distribution (bands)
    score_distribution = {
        "outstanding": 0,  # 85-100
        "exceeds": 0,      # 70-84
        "meets": 0,        # 50-69
        "below": 0,        # 0-49
    }

    scored_cards = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id,
        EmployeeScorecardInstance.total_weighted_score.isnot(None)
    ).all()

    for sc in scored_cards:
        if sc.total_weighted_score is None:
            continue
        score = float(sc.total_weighted_score)
        if score >= 85:
            score_distribution["outstanding"] += 1
        elif score >= 70:
            score_distribution["exceeds"] += 1
        elif score >= 50:
            score_distribution["meets"] += 1
        else:
            score_distribution["below"] += 1

    # Top performers
    top_performers_query = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id,
        EmployeeScorecardInstance.total_weighted_score.isnot(None)
    ).order_by(EmployeeScorecardInstance.total_weighted_score.desc()).limit(5).all()

    top_performers = []
    for sc in top_performers_query:
        emp = db.query(Employee).filter(Employee.id == sc.employee_id).first()
        if emp:
            top_performers.append({
                "employee_id": sc.employee_id,
                "employee_name": emp.name,
                "department": emp.department,
                "score": float(sc.total_weighted_score) if sc.total_weighted_score else None,
            })

    # Improvement needed (bottom performers)
    improvement_query = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id,
        EmployeeScorecardInstance.total_weighted_score.isnot(None),
        EmployeeScorecardInstance.total_weighted_score < 50
    ).order_by(EmployeeScorecardInstance.total_weighted_score).limit(5).all()

    improvement_needed = []
    for sc in improvement_query:
        emp = db.query(Employee).filter(Employee.id == sc.employee_id).first()
        if emp:
            improvement_needed.append({
                "employee_id": sc.employee_id,
                "employee_name": emp.name,
                "department": emp.department,
                "score": float(sc.total_weighted_score) if sc.total_weighted_score else None,
            })

    return DashboardSummary(
        active_period={
            "id": period.id,
            "code": period.code,
            "name": period.name,
            "status": period.status.value if hasattr(period.status, 'value') else period.status,
        },
        total_employees=total_employees,
        scorecards_generated=scorecards_generated,
        scorecards_computed=scorecards_computed,
        scorecards_in_review=scorecards_in_review,
        scorecards_finalized=scorecards_finalized,
        avg_score=avg_score,
        score_distribution=score_distribution,
        top_performers=top_performers,
        improvement_needed=improvement_needed,
    )


@router.get("/team", response_model=List[TeamPerformance], dependencies=[Depends(Require("performance:read"))])
async def get_team_performance(
    period_id: int,
    db: Session = Depends(get_db),
):
    """Get performance by department/team."""
    # Get distinct departments from employees with scorecards
    results = db.query(
        Employee.department,
        func.count(EmployeeScorecardInstance.id).label('count'),
        func.avg(EmployeeScorecardInstance.total_weighted_score).label('avg_score'),
        func.min(EmployeeScorecardInstance.total_weighted_score).label('min_score'),
        func.max(EmployeeScorecardInstance.total_weighted_score).label('max_score'),
        func.sum(
            case((EmployeeScorecardInstance.status == 'finalized', 1), else_=0)
        ).label('finalized_count'),
    ).join(
        EmployeeScorecardInstance, EmployeeScorecardInstance.employee_id == Employee.id
    ).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id
    ).group_by(Employee.department).all()

    return [
        TeamPerformance(
            department=r.department or "Unassigned",
            employee_count=r.count,
            avg_score=float(r.avg_score) if r.avg_score else None,
            min_score=float(r.min_score) if r.min_score else None,
            max_score=float(r.max_score) if r.max_score else None,
            finalized_count=r.finalized_count or 0,
        )
        for r in results
    ]


@router.get("/trends", response_model=List[ScoreTrend], dependencies=[Depends(Require("performance:read"))])
async def get_score_trends(
    employee_id: Optional[int] = None,
    department: Optional[str] = None,
    limit: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Get historical score trends."""
    # Get recent finalized periods
    periods = db.query(EvaluationPeriod).filter(
        EvaluationPeriod.status == 'finalized'
    ).order_by(EvaluationPeriod.end_date.desc()).limit(limit).all()

    periods = list(reversed(periods))  # Chronological order

    trends = []
    for period in periods:
        query = db.query(
            func.avg(EmployeeScorecardInstance.total_weighted_score).label('avg_score'),
            func.count(EmployeeScorecardInstance.id).label('count'),
        ).filter(
            EmployeeScorecardInstance.evaluation_period_id == period.id,
            EmployeeScorecardInstance.total_weighted_score.isnot(None)
        )

        if employee_id:
            query = query.filter(EmployeeScorecardInstance.employee_id == employee_id)

        if department:
            query = query.join(
                Employee, EmployeeScorecardInstance.employee_id == Employee.id
            ).filter(Employee.department == department)

        result = query.first()

        trends.append(ScoreTrend(
            period_code=period.code,
            period_name=period.name,
            avg_score=float(result.avg_score) if result.avg_score else None,
            employee_count=result.count or 0,
        ))

    return trends


@router.get("/distribution", response_model=List[ScoreDistribution], dependencies=[Depends(Require("performance:read"))])
async def get_score_distribution(
    period_id: int,
    db: Session = Depends(get_db),
):
    """Get score distribution breakdown."""
    bands = [
        {"rating": "Outstanding", "min": 85, "max": 100},
        {"rating": "Exceeds Expectations", "min": 70, "max": 84.99},
        {"rating": "Meets Expectations", "min": 50, "max": 69.99},
        {"rating": "Below Expectations", "min": 0, "max": 49.99},
    ]

    total_scored = db.query(func.count(EmployeeScorecardInstance.id)).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id,
        EmployeeScorecardInstance.total_weighted_score.isnot(None)
    ).scalar() or 0

    results = []
    for band in bands:
        count = db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.total_weighted_score >= band["min"],
            EmployeeScorecardInstance.total_weighted_score <= band["max"],
        ).scalar() or 0

        percentage = (count / total_scored * 100) if total_scored > 0 else 0

        results.append(ScoreDistribution(
            rating=str(band.get("rating", "")),
            min_score=float(band.get("min", 0)),
            max_score=float(band.get("max", 0)),
            count=count,
            percentage=round(percentage, 1),
        ))

    return results


@router.get("/bonus-eligibility", response_model=List[BonusEligibility], dependencies=[Depends(Require("performance:read"))])
async def get_bonus_eligibility(
    period_id: int,
    policy_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get bonus eligibility based on performance scores and policy."""
    # Get policy
    if policy_id:
        policy = db.query(BonusPolicy).filter(BonusPolicy.id == policy_id).first()
    else:
        policy = db.query(BonusPolicy).filter(BonusPolicy.is_active == True).first()

    if not policy:
        raise HTTPException(status_code=404, detail="No active bonus policy found")

    score_bands: List[Dict[str, Any]] = policy.score_bands or []

    # Get finalized scorecards
    scorecards = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id,
        EmployeeScorecardInstance.status == 'finalized',
        EmployeeScorecardInstance.total_weighted_score.isnot(None)
    ).all()

    results = []
    for sc in scorecards:
        emp = db.query(Employee).filter(Employee.id == sc.employee_id).first()
        if not emp:
            continue

        score = float(sc.total_weighted_score) if sc.total_weighted_score else 0
        bonus_factor = 0
        bonus_band = "Below Expectations"

        for band in score_bands:
            if band.get('min', 0) <= score <= band.get('max', 100):
                bonus_factor = band.get('factor', 0)
                bonus_band = band.get('label', 'Unknown')
                break

        results.append(BonusEligibility(
            employee_id=sc.employee_id,
            employee_name=emp.name,
            department=emp.department,
            final_score=score,
            rating=sc.final_rating,
            bonus_factor=bonus_factor,
            bonus_band=bonus_band,
        ))

    # Sort by score descending
    results.sort(key=lambda x: x.final_score or 0, reverse=True)

    return results


@router.get("/kra-breakdown", dependencies=[Depends(Require("performance:read"))])
async def get_kra_breakdown(
    period_id: int,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get average scores breakdown by KRA."""
    query = db.query(
        KRADefinition.code,
        KRADefinition.name,
        func.avg(KRAResult.final_score).label('avg_score'),
        func.count(KRAResult.id).label('count'),
    ).join(
        KRAResult, KRAResult.kra_id == KRADefinition.id
    ).join(
        EmployeeScorecardInstance, KRAResult.scorecard_instance_id == EmployeeScorecardInstance.id
    ).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id,
        KRAResult.final_score.isnot(None)
    )

    if department:
        query = query.join(
            Employee, EmployeeScorecardInstance.employee_id == Employee.id
        ).filter(Employee.department == department)

    results = query.group_by(KRADefinition.id).all()

    return [
        {
            "kra_code": r.code,
            "kra_name": r.name,
            "avg_score": float(r.avg_score) if r.avg_score else None,
            "count": r.count,
        }
        for r in results
    ]


@router.get("/export", dependencies=[Depends(Require("performance:read"))])
async def export_performance_data(
    period_id: int,
    format: str = Query("csv", regex="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
):
    """Export performance data for a period."""
    # TODO: Implement actual file export
    # For now, return data that would be exported

    scorecards = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id,
        EmployeeScorecardInstance.status == 'finalized'
    ).all()

    export_data = []
    for sc in scorecards:
        emp = db.query(Employee).filter(Employee.id == sc.employee_id).first()
        if not emp:
            continue

        export_data.append({
            "employee_code": emp.erpnext_id,
            "employee_name": emp.name,
            "department": emp.department,
            "designation": emp.designation,
            "total_score": float(sc.total_weighted_score) if sc.total_weighted_score else None,
            "rating": sc.final_rating,
            "status": sc.status.value if hasattr(sc.status, 'value') else sc.status,
            "finalized_at": sc.finalized_at.isoformat() if sc.finalized_at else None,
        })

    return {
        "format": format,
        "record_count": len(export_data),
        "data": export_data,
        "message": "Export data prepared. Actual file download not yet implemented."
    }


# ============= MANAGER/TEAM ENDPOINTS =============

@router.get("/manager/{manager_id}/team", dependencies=[Depends(Require("performance:team"))])
async def get_manager_team_performance(
    manager_id: int,
    period_id: int,
    include_indirect: bool = Query(True, description="Include indirect reports (skip-level)"),
    db: Session = Depends(get_db),
):
    """
    Get performance summary for a manager's team.

    Includes all direct reports and optionally indirect reports.
    Returns aggregated stats, score distribution, and individual details.
    """
    service = PerformanceService(db)
    return service.get_team_performance(manager_id, period_id, include_indirect)


@router.get("/manager/{manager_id}/org-tree", dependencies=[Depends(Require("performance:team"))])
async def get_manager_org_tree(
    manager_id: int,
    period_id: int,
    max_depth: int = Query(3, ge=1, le=5, description="Max hierarchy levels to include"),
    db: Session = Depends(get_db),
):
    """
    Get hierarchical org tree with performance data.

    Returns a tree structure showing the manager, their direct reports,
    and recursively their reports, with performance scores at each node.
    """
    service = PerformanceService(db)
    tree = service.get_org_tree_performance(manager_id, period_id, max_depth)

    if not tree:
        raise HTTPException(status_code=404, detail="Manager not found")

    return tree


@router.get("/manager/{manager_id}/hierarchy", dependencies=[Depends(Require("performance:read"))])
async def get_employee_hierarchy(
    manager_id: int,
    db: Session = Depends(get_db),
):
    """
    Get the reporting chain (managers) above an employee.

    Returns list from immediate manager up to top of org.
    """
    service = PerformanceService(db)
    return service.get_manager_hierarchy(manager_id)


@router.get("/departments/ranking", dependencies=[Depends(Require("performance:read"))])
async def get_department_ranking(
    period_id: int,
    db: Session = Depends(get_db),
):
    """
    Get departments ranked by average performance score.
    """
    service = PerformanceService(db)
    return service.get_department_ranking(period_id)


@router.get("/my-team", dependencies=[Depends(Require("performance:team"))])
async def get_my_team_performance(
    period_id: int,
    include_indirect: bool = Query(True),
    # current_user: User = Depends(get_current_user),  # TODO: implement auth
    db: Session = Depends(get_db),
):
    """
    Get performance summary for the current user's team.

    Requires the current user to be linked to an employee record.
    """
    # TODO: Get employee_id from current_user
    # For now, return a placeholder
    return {
        "message": "Auth not implemented. Use /manager/{manager_id}/team instead.",
        "example_url": "/performance/analytics/manager/1/team?period_id=1"
    }


@router.get("/team-comparison", dependencies=[Depends(Require("performance:read"))])
async def compare_teams(
    period_id: int,
    manager_ids: str = Query(..., description="Comma-separated manager IDs"),
    db: Session = Depends(get_db),
):
    """
    Compare performance across multiple teams/managers.
    """
    service = PerformanceService(db)

    ids = [int(x.strip()) for x in manager_ids.split(",") if x.strip().isdigit()]
    if not ids:
        raise HTTPException(status_code=400, detail="No valid manager IDs provided")

    comparisons = []
    for manager_id in ids:
        team_data = service.get_team_performance(manager_id, period_id, include_indirect=True)
        if team_data.get("success"):
            comparisons.append({
                "manager_id": manager_id,
                "manager_name": team_data.get("manager_name"),
                "team_size": team_data.get("team_size"),
                "avg_score": team_data.get("stats", {}).get("avg_score"),
                "min_score": team_data.get("stats", {}).get("min_score"),
                "max_score": team_data.get("stats", {}).get("max_score"),
                "pending_reviews": team_data.get("pending_reviews"),
                "distribution": team_data.get("distribution"),
            })

    # Sort by avg score
    comparisons.sort(key=lambda x: x.get("avg_score") or 0, reverse=True)

    return {
        "period_id": period_id,
        "teams": comparisons,
        "best_team": comparisons[0] if comparisons else None,
    }


@router.get("/manager/{manager_id}/pending-reviews", dependencies=[Depends(Require("performance:review"))])
async def get_manager_pending_reviews(
    manager_id: int,
    period_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Get scorecards pending review from a manager's team.
    """
    service = PerformanceService(db)

    # Get team members
    team_members = service.get_team_members(manager_id, include_indirect=True)
    team_ids = [e.id for e in team_members]

    if not team_ids:
        return {"items": [], "total": 0}

    query = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.employee_id.in_(team_ids),
        EmployeeScorecardInstance.status.in_(['computed', 'in_review'])
    )

    if period_id:
        query = query.filter(EmployeeScorecardInstance.evaluation_period_id == period_id)

    scorecards = query.all()

    items = []
    for sc in scorecards:
        emp = db.query(Employee).filter(Employee.id == sc.employee_id).first()
        period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == sc.evaluation_period_id).first()

        items.append({
            "scorecard_id": sc.id,
            "employee_id": sc.employee_id,
            "employee_name": emp.name if emp else "Unknown",
            "department": emp.department if emp else None,
            "designation": emp.designation if emp else None,
            "period_id": sc.evaluation_period_id,
            "period_name": period.name if period else "",
            "status": sc.status.value if hasattr(sc.status, 'value') else str(sc.status),
            "score": float(sc.total_weighted_score) if sc.total_weighted_score else None,
            "updated_at": sc.updated_at.isoformat() if sc.updated_at else None,
        })

    # Sort by score descending
    def _score_key(item: Dict[str, Any]) -> float:
        score = item.get("score")
        return float(score) if score is not None else 0.0

    items.sort(key=_score_key, reverse=True)

    return {"items": items, "total": len(items)}
