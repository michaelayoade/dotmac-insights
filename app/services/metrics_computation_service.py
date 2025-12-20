"""
Metrics Computation Service - Core engine for computing KPI values and scores

Queries data from various sources (ticketing, field service, etc.) and computes
KPI values, scores, and weighted totals for employee scorecards.
"""
import logging
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy import func, and_, or_, false
from sqlalchemy.orm import Session

from app.models.performance import (
    KPIDefinition,
    KPIDataSource,
    KPIAggregation,
    ScoringMethod,
    KRAKPIMap,
    KRADefinition,
    ScorecardTemplate,
    ScorecardTemplateItem,
    EmployeeScorecardInstance,
    ScorecardInstanceStatus,
    EvaluationPeriod,
    KPIResult,
    KRAResult,
    KPIBinding,
)
from app.models.ticket import Ticket, TicketStatus
from app.models.field_service import ServiceOrder, ServiceOrderStatus
from app.models.crm import Opportunity, Activity, OpportunityStatus, ActivityStatus
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus
from app.models.employee import Employee

logger = logging.getLogger(__name__)


class MetricsComputationService:
    """Service for computing KPI metrics and scores."""

    def __init__(self, db: Session):
        self.db = db

    def compute_scorecard(self, scorecard_id: int) -> Dict[str, Any]:
        """
        Compute all KPI and KRA results for a single scorecard.

        Returns dict with computation results and any errors.
        """
        scorecard = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.id == scorecard_id
        ).first()

        if not scorecard:
            return {"success": False, "error": "Scorecard not found"}

        # Get period date range
        period = self.db.query(EvaluationPeriod).filter(
            EvaluationPeriod.id == scorecard.evaluation_period_id
        ).first()

        if not period:
            return {"success": False, "error": "Evaluation period not found"}

        # Get template with items
        template = self.db.query(ScorecardTemplate).filter(
            ScorecardTemplate.id == scorecard.template_id
        ).first()

        if not template:
            return {"success": False, "error": "Template not found"}

        template_items = self.db.query(ScorecardTemplateItem).filter(
            ScorecardTemplateItem.template_id == template.id
        ).all()

        # Clear existing results
        self.db.query(KPIResult).filter(KPIResult.scorecard_instance_id == scorecard_id).delete()
        self.db.query(KRAResult).filter(KRAResult.scorecard_instance_id == scorecard_id).delete()

        kra_scores = {}
        errors = []

        for item in template_items:
            kra = self.db.query(KRADefinition).filter(KRADefinition.id == item.kra_id).first()
            if not kra:
                continue

            # Get KPIs linked to this KRA
            kpi_mappings = self.db.query(KRAKPIMap).filter(KRAKPIMap.kra_id == kra.id).all()

            kpi_weighted_total = Decimal("0")
            kpi_weight_sum = Decimal("0")

            for kpi_map in kpi_mappings:
                kpi = self.db.query(KPIDefinition).filter(KPIDefinition.id == kpi_map.kpi_id).first()
                if not kpi:
                    continue

                try:
                    # Compute raw value
                    raw_value = self._compute_kpi_value(
                        kpi, scorecard.employee_id, period.start_date, period.end_date
                    )

                    # Get target value (check for binding override)
                    target_value = self._get_target_value(
                        kpi, scorecard.employee_id, period.start_date, period.end_date
                    )

                    # Compute score
                    computed_score = self._compute_score(kpi, raw_value, target_value)

                    # Get weightage in KRA
                    weightage = float(kpi_map.weightage or 0)

                    # Compute weighted score
                    weighted_score = (computed_score * Decimal(str(weightage))) / Decimal("100")

                    # Store KPI result
                    kpi_result = KPIResult(
                        scorecard_instance_id=scorecard_id,
                        kpi_id=kpi.id,
                        kra_id=kra.id,
                        raw_value=raw_value,
                        target_value=target_value,
                        computed_score=computed_score,
                        final_score=computed_score,  # Same initially, can be overridden
                        weightage_in_kra=Decimal(str(weightage)),
                        weighted_score=weighted_score,
                    )
                    self.db.add(kpi_result)

                    kpi_weighted_total += weighted_score
                    kpi_weight_sum += Decimal(str(weightage))

                except Exception as e:
                    logger.error(f"Error computing KPI {kpi.code}: {e}")
                    errors.append({"kpi_code": kpi.code, "error": str(e)})

            # Compute KRA score (weighted average of KPIs)
            kra_score = kpi_weighted_total if kpi_weight_sum > 0 else Decimal("0")

            # Get KRA weightage in scorecard
            kra_weightage = float(item.weightage or 0)

            # Store KRA result
            kra_result = KRAResult(
                scorecard_instance_id=scorecard_id,
                kra_id=kra.id,
                computed_score=kra_score,
                final_score=kra_score,
                weightage_in_scorecard=Decimal(str(kra_weightage)),
                weighted_score=(kra_score * Decimal(str(kra_weightage))) / Decimal("100"),
            )
            self.db.add(kra_result)
            kra_scores[kra.id] = kra_result

        # Compute total weighted score
        total_weighted_score = sum(
            float(kr.weighted_score or 0) for kr in kra_scores.values()
        )

        # Determine rating band
        final_rating = self._determine_rating(total_weighted_score)

        # Update scorecard
        scorecard.total_weighted_score = Decimal(str(total_weighted_score))
        scorecard.final_rating = final_rating
        scorecard.status = ScorecardInstanceStatus.COMPUTED

        self.db.commit()

        return {
            "success": True,
            "scorecard_id": scorecard_id,
            "total_score": total_weighted_score,
            "rating": final_rating,
            "kra_count": len(kra_scores),
            "errors": errors,
        }

    def _compute_kpi_value(
        self,
        kpi: KPIDefinition,
        employee_id: int,
        start_date: date,
        end_date: date,
    ) -> Optional[Decimal]:
        """
        Compute raw KPI value from data source.
        """
        if kpi.data_source == KPIDataSource.MANUAL:
            # Manual KPIs require manual entry
            return None

        elif kpi.data_source == KPIDataSource.TICKETING:
            return self._query_ticketing_kpi(kpi, employee_id, start_date, end_date)

        elif kpi.data_source == KPIDataSource.FIELD_SERVICE:
            return self._query_field_service_kpi(kpi, employee_id, start_date, end_date)

        elif kpi.data_source == KPIDataSource.CRM:
            return self._query_crm_kpi(kpi, employee_id, start_date, end_date)

        elif kpi.data_source == KPIDataSource.PROJECT:
            return self._query_project_kpi(kpi, employee_id, start_date, end_date)

        # TODO: Add more data sources (finance, attendance)
        else:
            logger.warning(f"Unsupported data source: {kpi.data_source}")
            return None

    def _query_ticketing_kpi(
        self,
        kpi: KPIDefinition,
        employee_id: int,
        start_date: date,
        end_date: date,
    ) -> Optional[Decimal]:
        """
        Query ticketing data for KPI computation.
        """
        config = kpi.query_config or {}

        # Base query with date filter
        base_query = self.db.query(Ticket).filter(
            Ticket.created_at >= datetime.combine(start_date, datetime.min.time()),
            Ticket.created_at <= datetime.combine(end_date, datetime.max.time()),
        )

        # Apply ownership filter (assigned to employee)
        # TODO: Make this configurable based on query_config
        base_query = base_query.filter(Ticket.assigned_employee_id == employee_id)

        # Apply status filter if specified
        if config.get('filter', {}).get('status'):
            base_query = base_query.filter(Ticket.status == config['filter']['status'])

        if kpi.aggregation == KPIAggregation.COUNT:
            result = base_query.count()
            return Decimal(str(result))

        elif kpi.aggregation == KPIAggregation.PERCENT:
            # For percent KPIs, we need numerator and denominator
            numerator_filter = config.get('numerator', {})
            denominator_filter = config.get('denominator', {})

            # Count denominator (total relevant tickets)
            denom_query = base_query
            if denominator_filter.get('status'):
                denom_query = denom_query.filter(Ticket.status == denominator_filter['status'])
            denominator = denom_query.count()

            if denominator == 0:
                return Decimal("0")

            # Count numerator (tickets meeting criteria)
            numer_query = base_query
            if numerator_filter.get('sla_met'):
                sla_met_column = getattr(Ticket, "sla_met", None)
                if sla_met_column is not None:
                    numer_query = numer_query.filter(sla_met_column.is_(True))
                else:
                    numer_query = numer_query.filter(
                        and_(
                            Ticket.resolution_by.isnot(None),
                            Ticket.resolution_date.isnot(None),
                            Ticket.resolution_date <= Ticket.resolution_by,
                        )
                    )
            if numerator_filter.get('reopened'):
                reopened_column = getattr(Ticket, "reopened", None)
                if reopened_column is not None:
                    numer_query = numer_query.filter(reopened_column.is_(True))
                else:
                    reopened_status = getattr(TicketStatus, "REOPENED", None)
                    if reopened_status is not None:
                        numer_query = numer_query.filter(Ticket.status == reopened_status)
                    else:
                        numer_query = numer_query.filter(false())
            numerator = numer_query.count()

            return Decimal(str((numerator / denominator) * 100)).quantize(Decimal("0.01"))

        elif kpi.aggregation == KPIAggregation.AVG:
            field = config.get('field')
            if field and hasattr(Ticket, field):
                result = base_query.with_entities(func.avg(getattr(Ticket, field))).scalar()
                return Decimal(str(result or 0)).quantize(Decimal("0.01"))

        return None

    def _query_field_service_kpi(
        self,
        kpi: KPIDefinition,
        employee_id: int,
        start_date: date,
        end_date: date,
    ) -> Optional[Decimal]:
        """
        Query field service data for KPI computation.
        """
        config = kpi.query_config or {}

        # Base query with date filter
        base_query = self.db.query(ServiceOrder).filter(
            ServiceOrder.created_at >= datetime.combine(start_date, datetime.min.time()),
            ServiceOrder.created_at <= datetime.combine(end_date, datetime.max.time()),
        )

        # Apply ownership filter (technician)
        base_query = base_query.filter(ServiceOrder.assigned_technician_id == employee_id)

        # Apply status filter if specified
        if config.get('filter', {}).get('status'):
            base_query = base_query.filter(ServiceOrder.status == config['filter']['status'])

        # Apply order type filter (e.g., preventive maintenance)
        if config.get('filter', {}).get('order_type'):
            base_query = base_query.filter(ServiceOrder.order_type == config['filter']['order_type'])

        if kpi.aggregation == KPIAggregation.COUNT:
            result = base_query.count()
            return Decimal(str(result))

        elif kpi.aggregation == KPIAggregation.PERCENT:
            numerator_filter = config.get('numerator', {})
            denominator_filter = config.get('denominator', {})

            # Count denominator
            denom_query = base_query
            if denominator_filter.get('status'):
                denom_query = denom_query.filter(ServiceOrder.status == denominator_filter['status'])
            denominator = denom_query.count()

            if denominator == 0:
                return Decimal("0")

            # Count numerator
            numer_query = base_query
            if numerator_filter.get('status'):
                numer_query = numer_query.filter(ServiceOrder.status == numerator_filter['status'])
            if numerator_filter.get('first_time_fix'):
                first_time_fix_column = getattr(ServiceOrder, "first_time_fix", None)
                if first_time_fix_column is not None:
                    numer_query = numer_query.filter(first_time_fix_column.is_(True))
                else:
                    numer_query = numer_query.filter(ServiceOrder.status == ServiceOrderStatus.COMPLETED)
            if numerator_filter.get('arrived_on_time'):
                arrived_on_time_column = getattr(ServiceOrder, "arrived_on_time", None)
                if arrived_on_time_column is not None:
                    numer_query = numer_query.filter(arrived_on_time_column.is_(True))
                else:
                    numer_query = numer_query.filter(false())
            numerator = numer_query.count()

            return Decimal(str((numerator / denominator) * 100)).quantize(Decimal("0.01"))

        elif kpi.aggregation == KPIAggregation.AVG:
            field = config.get('field')
            if field and hasattr(ServiceOrder, field):
                result = base_query.with_entities(func.avg(getattr(ServiceOrder, field))).scalar()
                return Decimal(str(result or 0)).quantize(Decimal("0.01"))

        return None

    def _query_crm_kpi(
        self,
        kpi: KPIDefinition,
        employee_id: int,
        start_date: date,
        end_date: date,
    ) -> Optional[Decimal]:
        """
        Query CRM data (opportunities, activities) for KPI computation.
        """
        config = kpi.query_config or {}
        table = config.get('table', 'opportunities')
        employee_field = config.get('employee_field', 'owner_id')

        if table == 'opportunities':
            return self._query_opportunity_kpi(config, kpi, employee_id, employee_field, start_date, end_date)
        elif table == 'activities':
            return self._query_activity_kpi(config, kpi, employee_id, employee_field, start_date, end_date)

        return None

    def _query_opportunity_kpi(
        self,
        config: dict,
        kpi: KPIDefinition,
        employee_id: int,
        employee_field: str,
        start_date: date,
        end_date: date,
    ) -> Optional[Decimal]:
        """Query opportunity data for KPI computation."""
        # Base query with date filter
        base_query = self.db.query(Opportunity).filter(
            Opportunity.created_at >= datetime.combine(start_date, datetime.min.time()),
            Opportunity.created_at <= datetime.combine(end_date, datetime.max.time()),
        )

        # Apply employee filter based on config
        if employee_field == 'owner_id':
            base_query = base_query.filter(Opportunity.owner_id == employee_id)
        elif employee_field == 'sales_person_id':
            base_query = base_query.filter(Opportunity.sales_person_id == employee_id)

        # Apply status filter if specified
        filter_config = config.get('filter', {})
        if filter_config.get('status'):
            status_map = {
                'open': OpportunityStatus.OPEN,
                'won': OpportunityStatus.WON,
                'lost': OpportunityStatus.LOST,
            }
            status = status_map.get(filter_config['status'].lower())
            if status:
                base_query = base_query.filter(Opportunity.status == status)

        if kpi.aggregation == KPIAggregation.COUNT:
            result = base_query.count()
            return Decimal(str(result))

        elif kpi.aggregation == KPIAggregation.SUM:
            field = config.get('field', 'deal_value')
            if hasattr(Opportunity, field):
                result = base_query.with_entities(func.sum(getattr(Opportunity, field))).scalar()
                return Decimal(str(result or 0)).quantize(Decimal("0.01"))

        elif kpi.aggregation == KPIAggregation.AVG:
            field = config.get('field', 'deal_value')
            # Special handling for sales_cycle_days
            if field == 'sales_cycle_days':
                # Calculate average days from created_at to actual_close_date
                closed_opps = base_query.filter(
                    Opportunity.actual_close_date.isnot(None)
                ).all()
                if not closed_opps:
                    return Decimal("0")
                total_days = sum(
                    (opp.actual_close_date - opp.created_at.date()).days
                    for opp in closed_opps if opp.actual_close_date
                )
                return Decimal(str(total_days / len(closed_opps))).quantize(Decimal("0.01"))
            elif hasattr(Opportunity, field):
                result = base_query.with_entities(func.avg(getattr(Opportunity, field))).scalar()
                return Decimal(str(result or 0)).quantize(Decimal("0.01"))

        elif kpi.aggregation == KPIAggregation.PERCENT:
            numerator_filter = config.get('numerator', {})
            denominator_filter = config.get('denominator', {})

            # Denominator query
            denom_query = base_query
            if denominator_filter.get('status_in'):
                statuses = [
                    {'open': OpportunityStatus.OPEN, 'won': OpportunityStatus.WON, 'lost': OpportunityStatus.LOST}
                    .get(s.lower())
                    for s in denominator_filter['status_in']
                ]
                statuses = [s for s in statuses if s]
                if statuses:
                    denom_query = denom_query.filter(Opportunity.status.in_(statuses))
            denominator = denom_query.count()

            if denominator == 0:
                return Decimal("0")

            # Numerator query
            numer_query = base_query
            if numerator_filter.get('status'):
                status_map = {'open': OpportunityStatus.OPEN, 'won': OpportunityStatus.WON, 'lost': OpportunityStatus.LOST}
                status = status_map.get(numerator_filter['status'].lower())
                if status:
                    numer_query = numer_query.filter(Opportunity.status == status)
            if denominator_filter.get('status_in'):
                statuses = [
                    {'open': OpportunityStatus.OPEN, 'won': OpportunityStatus.WON, 'lost': OpportunityStatus.LOST}
                    .get(s.lower())
                    for s in denominator_filter['status_in']
                ]
                statuses = [s for s in statuses if s]
                if statuses:
                    numer_query = numer_query.filter(Opportunity.status.in_(statuses))
            numerator = numer_query.count()

            return Decimal(str((numerator / denominator) * 100)).quantize(Decimal("0.01"))

        return None

    def _query_activity_kpi(
        self,
        config: dict,
        kpi: KPIDefinition,
        employee_id: int,
        employee_field: str,
        start_date: date,
        end_date: date,
    ) -> Optional[Decimal]:
        """Query activity data for KPI computation."""
        # Base query with date filter
        base_query = self.db.query(Activity).filter(
            Activity.created_at >= datetime.combine(start_date, datetime.min.time()),
            Activity.created_at <= datetime.combine(end_date, datetime.max.time()),
        )

        # Apply employee filter
        if employee_field == 'assigned_to_id':
            base_query = base_query.filter(Activity.assigned_to_id == employee_id)
        elif employee_field == 'owner_id':
            base_query = base_query.filter(Activity.owner_id == employee_id)

        # Apply status filter
        filter_config = config.get('filter', {})
        if filter_config.get('status'):
            status_map = {
                'planned': ActivityStatus.PLANNED,
                'completed': ActivityStatus.COMPLETED,
                'cancelled': ActivityStatus.CANCELLED,
            }
            status = status_map.get(filter_config['status'].lower())
            if status:
                base_query = base_query.filter(Activity.status == status)

        if kpi.aggregation == KPIAggregation.COUNT:
            result = base_query.count()
            return Decimal(str(result))

        elif kpi.aggregation == KPIAggregation.AVG:
            field = config.get('field', 'duration_minutes')
            if hasattr(Activity, field):
                result = base_query.with_entities(func.avg(getattr(Activity, field))).scalar()
                return Decimal(str(result or 0)).quantize(Decimal("0.01"))

        return None

    def _query_project_kpi(
        self,
        kpi: KPIDefinition,
        employee_id: int,
        start_date: date,
        end_date: date,
    ) -> Optional[Decimal]:
        """
        Query project/task data for KPI computation.
        """
        config = kpi.query_config or {}
        table = config.get('table', 'projects')
        employee_field = config.get('employee_field', 'project_manager_id')

        if table == 'projects':
            return self._query_project_table_kpi(config, kpi, employee_id, employee_field, start_date, end_date)
        elif table == 'tasks':
            return self._query_task_kpi(config, kpi, employee_id, employee_field, start_date, end_date)

        return None

    def _query_project_table_kpi(
        self,
        config: dict,
        kpi: KPIDefinition,
        employee_id: int,
        employee_field: str,
        start_date: date,
        end_date: date,
    ) -> Optional[Decimal]:
        """Query project table for KPI computation."""
        # Base query with date filter
        base_query = self.db.query(Project).filter(
            Project.created_at >= datetime.combine(start_date, datetime.min.time()),
            Project.created_at <= datetime.combine(end_date, datetime.max.time()),
            Project.is_deleted == False,
        )

        # Apply employee filter (project manager)
        if employee_field == 'project_manager_id':
            base_query = base_query.filter(Project.project_manager_id == employee_id)

        # Apply status filter
        filter_config = config.get('filter', {})
        if filter_config.get('status'):
            status_map = {
                'open': ProjectStatus.OPEN,
                'completed': ProjectStatus.COMPLETED,
                'cancelled': ProjectStatus.CANCELLED,
                'on_hold': ProjectStatus.ON_HOLD,
            }
            status = status_map.get(filter_config['status'].lower())
            if status:
                base_query = base_query.filter(Project.status == status)

        if kpi.aggregation == KPIAggregation.COUNT:
            result = base_query.count()
            return Decimal(str(result))

        elif kpi.aggregation == KPIAggregation.AVG:
            field = config.get('field')
            if field and hasattr(Project, field):
                result = base_query.with_entities(func.avg(getattr(Project, field))).scalar()
                return Decimal(str(result or 0)).quantize(Decimal("0.01"))

        elif kpi.aggregation == KPIAggregation.PERCENT:
            numerator_filter = config.get('numerator', {})

            # Denominator is base_query count
            denominator = base_query.count()
            if denominator == 0:
                return Decimal("0")

            # Numerator query
            numer_query = base_query

            # On-time delivery: actual_end_date <= expected_end_date
            if numerator_filter.get('on_time'):
                numer_query = numer_query.filter(
                    Project.actual_end_date.isnot(None),
                    Project.expected_end_date.isnot(None),
                    Project.actual_end_date <= Project.expected_end_date
                )

            # Within budget: total_costing_amount <= estimated_costing
            if numerator_filter.get('within_budget'):
                numer_query = numer_query.filter(
                    Project.total_costing_amount <= Project.estimated_costing
                )

            numerator = numer_query.count()
            return Decimal(str((numerator / denominator) * 100)).quantize(Decimal("0.01"))

        return None

    def _query_task_kpi(
        self,
        config: dict,
        kpi: KPIDefinition,
        employee_id: int,
        employee_field: str,
        start_date: date,
        end_date: date,
    ) -> Optional[Decimal]:
        """Query task table for KPI computation."""
        # Base query with date filter
        base_query = self.db.query(Task).filter(
            Task.created_at >= datetime.combine(start_date, datetime.min.time()),
            Task.created_at <= datetime.combine(end_date, datetime.max.time()),
        )

        # Apply employee filter
        # Tasks use assigned_to (string email/user), need to map to employee
        if employee_field == 'assigned_to':
            # Tasks store the assignee as a string (typically email/username).
            # Use the employee's email as the matching key; if missing, no results.
            employee_email = self.db.query(Employee.email).filter(Employee.id == employee_id).scalar()
            if employee_email:
                base_query = base_query.filter(Task.assigned_to == employee_email)
            else:
                return Decimal("0")

        # Apply status filter
        filter_config = config.get('filter', {})
        if filter_config.get('status'):
            status_map = {
                'open': TaskStatus.OPEN,
                'working': TaskStatus.WORKING,
                'pending_review': TaskStatus.PENDING_REVIEW,
                'overdue': TaskStatus.OVERDUE,
                'completed': TaskStatus.COMPLETED,
                'cancelled': TaskStatus.CANCELLED,
            }
            status = status_map.get(filter_config['status'].lower())
            if status:
                base_query = base_query.filter(Task.status == status)

        if kpi.aggregation == KPIAggregation.COUNT:
            result = base_query.count()
            return Decimal(str(result))

        elif kpi.aggregation == KPIAggregation.AVG:
            field = config.get('field')
            # Special handling for time variance
            if field == 'time_variance_percent':
                tasks = base_query.filter(Task.expected_time > 0).all()
                if not tasks:
                    return Decimal("0")
                total_variance = sum(
                    abs(float(t.actual_time - t.expected_time) / float(t.expected_time) * 100)
                    for t in tasks if t.expected_time > 0
                )
                return Decimal(str(total_variance / len(tasks))).quantize(Decimal("0.01"))
            elif field and hasattr(Task, field):
                result = base_query.with_entities(func.avg(getattr(Task, field))).scalar()
                return Decimal(str(result or 0)).quantize(Decimal("0.01"))

        elif kpi.aggregation == KPIAggregation.PERCENT:
            numerator_filter = config.get('numerator', {})

            # Denominator is base_query count
            denominator = base_query.count()
            if denominator == 0:
                return Decimal("0")

            # Numerator query
            numer_query = base_query

            # On-time completion: completed_on <= exp_end_date OR act_end_date <= exp_end_date
            if numerator_filter.get('on_time'):
                numer_query = numer_query.filter(
                    or_(
                        and_(Task.completed_on.isnot(None), Task.exp_end_date.isnot(None),
                             Task.completed_on <= Task.exp_end_date),
                        and_(Task.act_end_date.isnot(None), Task.exp_end_date.isnot(None),
                             Task.act_end_date <= Task.exp_end_date)
                    )
                )

            numerator = numer_query.count()
            return Decimal(str((numerator / denominator) * 100)).quantize(Decimal("0.01"))

        return None

    def _get_target_value(
        self,
        kpi: KPIDefinition,
        employee_id: int,
        start_date: date,
        end_date: date,
    ) -> Optional[Decimal]:
        """
        Get target value for KPI, checking for employee-specific overrides.
        """
        # Check for employee-specific binding
        binding = self.db.query(KPIBinding).filter(
            KPIBinding.kpi_id == kpi.id,
            KPIBinding.employee_id == employee_id,
            or_(
                KPIBinding.effective_from.is_(None),
                KPIBinding.effective_from <= start_date
            ),
            or_(
                KPIBinding.effective_to.is_(None),
                KPIBinding.effective_to >= end_date
            )
        ).first()

        if binding and binding.target_override:
            return binding.target_override

        # Fall back to KPI default target
        return kpi.target_value

    def _compute_score(
        self,
        kpi: KPIDefinition,
        raw_value: Optional[Decimal],
        target_value: Optional[Decimal],
    ) -> Decimal:
        """
        Compute score based on KPI scoring method.

        Returns score from 0 to 100.
        """
        if raw_value is None or target_value is None:
            return Decimal("0")

        raw = float(raw_value)
        target = float(target_value)

        if target == 0:
            return Decimal("0")

        if kpi.scoring_method == ScoringMethod.LINEAR:
            return self._linear_score(kpi, raw, target)

        elif kpi.scoring_method == ScoringMethod.THRESHOLD:
            return self._threshold_score(kpi, raw)

        elif kpi.scoring_method == ScoringMethod.BAND:
            return self._band_score(kpi, raw, target)

        elif kpi.scoring_method == ScoringMethod.BINARY:
            if kpi.higher_is_better:
                return Decimal("100") if raw >= target else Decimal("0")
            else:
                return Decimal("100") if raw <= target else Decimal("0")

        return Decimal("0")

    def _linear_score(self, kpi: KPIDefinition, raw: float, target: float) -> Decimal:
        """Linear scoring: proportional to achievement vs target."""
        min_val = float(kpi.min_value or 0)
        max_val = float(kpi.max_value or target * 2)

        if kpi.higher_is_better:
            # Higher is better: score = (actual - min) / (target - min) * 100
            if target <= min_val:
                return Decimal("100") if raw >= target else Decimal("0")
            score = ((raw - min_val) / (target - min_val)) * 100
        else:
            # Lower is better: score = (target - actual) / (target - max) * 100
            # Or more intuitively: score = target / actual * 100
            if raw <= 0:
                return Decimal("100")
            score = (target / raw) * 100

        # Cap at 100
        score = min(max(score, 0), 100)
        return Decimal(str(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _threshold_score(self, kpi: KPIDefinition, raw: float) -> Decimal:
        """Threshold/banded scoring from config."""
        thresholds = kpi.threshold_config or {}
        bands = thresholds.get('bands', [])

        for band in bands:
            min_val = band.get('min', float('-inf'))
            max_val = band.get('max', float('inf'))
            score = band.get('score', 0)

            if min_val <= raw <= max_val:
                return Decimal(str(score))

        return Decimal("0")

    def _band_score(self, kpi: KPIDefinition, raw: float, target: float) -> Decimal:
        """Band scoring with target as center."""
        min_val = float(kpi.min_value or 0)
        max_val = float(kpi.max_value or target * 2)

        # Score based on distance from target within band
        if kpi.higher_is_better:
            if raw >= target:
                return Decimal("100")
            elif raw <= min_val:
                return Decimal("0")
            else:
                score = ((raw - min_val) / (target - min_val)) * 100
        else:
            if raw <= target:
                return Decimal("100")
            elif raw >= max_val:
                return Decimal("0")
            else:
                score = ((max_val - raw) / (max_val - target)) * 100

        return Decimal(str(min(max(score, 0), 100))).quantize(Decimal("0.01"))

    def _determine_rating(self, total_score: float) -> str:
        """Determine rating band from total score."""
        if total_score >= 85:
            return "Outstanding"
        elif total_score >= 70:
            return "Exceeds Expectations"
        elif total_score >= 50:
            return "Meets Expectations"
        else:
            return "Below Expectations"

    def compute_period(self, period_id: int) -> Dict[str, Any]:
        """
        Compute all scorecards for a period.
        """
        period = self.db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
        if not period:
            return {"success": False, "error": "Period not found"}

        scorecards = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.status.in_([
                ScorecardInstanceStatus.PENDING,
                ScorecardInstanceStatus.COMPUTING,
                'pending',
                'computing'
            ])
        ).all()

        results: Dict[str, Any] = {
            "total": len(scorecards),
            "computed": 0,
            "failed": 0,
            "errors": [],
        }

        for scorecard in scorecards:
            try:
                result = self.compute_scorecard(scorecard.id)
                if result.get("success"):
                    results["computed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "scorecard_id": scorecard.id,
                        "error": result.get("error")
                    })
            except Exception as e:
                logger.error(f"Error computing scorecard {scorecard.id}: {e}")
                results["failed"] += 1
                results["errors"].append({
                    "scorecard_id": scorecard.id,
                    "error": str(e)
                })

        return results
