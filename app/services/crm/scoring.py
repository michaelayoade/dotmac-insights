"""Lead Scoring Service.

Provides business logic for automated lead scoring:
- Rule-based scoring (attribute, behavior, engagement)
- Score calculation and updates
- Score decay over time
- Score analytics and distribution
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Any

from sqlalchemy import select, func, and_, or_, case, update
from sqlalchemy.orm import Session

from app.models.crm_engagement import LeadScoringRule
from app.models.party import Party

from .scoring_types import (
    ScoringRuleFilters,
    ScoringRuleCreateData,
    ScoringRuleUpdateData,
    ScoringCondition,
    ScoreAdjustment,
    LeadScoreResult,
    ScoringRuleSummary,
    ScoreDistribution,
    ScoreHistory,
)


# Score thresholds for grading
GRADE_THRESHOLDS = {
    "A": 80,
    "B": 60,
    "C": 40,
    "D": 20,
    "F": 0,
}

QUALIFICATION_THRESHOLD = 60  # Score needed to be "qualified"


class LeadScoringService:
    """Service for lead scoring operations."""

    def __init__(self, session: Session, company_id: int, user_id: int):
        self.session = session
        self.company_id = company_id
        self.user_id = user_id

    # -------------------------------------------------------------------------
    # Rule CRUD
    # -------------------------------------------------------------------------

    def list_rules(
        self,
        filters: Optional[ScoringRuleFilters] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[LeadScoringRule], int]:
        """List scoring rules with optional filters."""
        query = select(LeadScoringRule).where(
            LeadScoringRule.company_id == self.company_id
        )

        if filters:
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.where(
                    or_(
                        LeadScoringRule.name.ilike(search_term),
                        LeadScoringRule.description.ilike(search_term),
                    )
                )

            if filters.rule_type:
                query = query.where(LeadScoringRule.rule_type == filters.rule_type)

            if filters.is_active is not None:
                query = query.where(LeadScoringRule.is_active == filters.is_active)

            if filters.category:
                query = query.where(LeadScoringRule.category == filters.category)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = self.session.execute(count_query).scalar() or 0

        # Fetch with pagination
        query = (
            query.order_by(LeadScoringRule.priority, LeadScoringRule.name)
            .offset(skip)
            .limit(limit)
        )
        rules = list(self.session.execute(query).scalars().all())

        return rules, total

    def get_rule(self, rule_id: int) -> Optional[LeadScoringRule]:
        """Get a scoring rule by ID."""
        query = select(LeadScoringRule).where(
            LeadScoringRule.id == rule_id,
            LeadScoringRule.company_id == self.company_id,
        )
        return self.session.execute(query).scalar_one_or_none()

    def create_rule(self, data: ScoringRuleCreateData) -> LeadScoringRule:
        """Create a new scoring rule."""
        rule = LeadScoringRule(
            company_id=self.company_id,
            name=data.name,
            description=data.description,
            rule_type=data.rule_type,
            category=data.category,
            conditions=self._serialize_conditions(data.conditions),
            score_change=data.score_change,
            decay_enabled=data.decay_enabled,
            decay_days=data.decay_days,
            decay_amount=data.decay_amount,
            priority=data.priority,
            is_active=data.is_active,
            created_by=self.user_id,
        )
        self.session.add(rule)
        self.session.flush()
        return rule

    def update_rule(
        self, rule_id: int, data: ScoringRuleUpdateData
    ) -> Optional[LeadScoringRule]:
        """Update a scoring rule."""
        rule = self.get_rule(rule_id)
        if not rule:
            return None

        if data.name is not None:
            rule.name = data.name
        if data.description is not None:
            rule.description = data.description
        if data.rule_type is not None:
            rule.rule_type = data.rule_type
        if data.category is not None:
            rule.category = data.category
        if data.conditions is not None:
            rule.conditions = self._serialize_conditions(data.conditions)
        if data.score_change is not None:
            rule.score_change = data.score_change
        if data.decay_enabled is not None:
            rule.decay_enabled = data.decay_enabled
        if data.decay_days is not None:
            rule.decay_days = data.decay_days
        if data.decay_amount is not None:
            rule.decay_amount = data.decay_amount
        if data.priority is not None:
            rule.priority = data.priority
        if data.is_active is not None:
            rule.is_active = data.is_active

        rule.updated_at = datetime.utcnow()
        self.session.flush()
        return rule

    def delete_rule(self, rule_id: int) -> bool:
        """Delete a scoring rule."""
        rule = self.get_rule(rule_id)
        if not rule:
            return False

        self.session.delete(rule)
        self.session.flush()
        return True

    # -------------------------------------------------------------------------
    # Scoring Operations
    # -------------------------------------------------------------------------

    def score_lead(self, party_id: int) -> Optional[LeadScoreResult]:
        """Calculate and apply score for a single lead."""
        party = self.session.execute(
            select(Party).where(
                Party.id == party_id, Party.company_id == self.company_id
            )
        ).scalar_one_or_none()

        if not party:
            return None

        previous_score = party.engagement_score or 0
        adjustments: List[ScoreAdjustment] = []
        new_score = 0

        # Get active rules ordered by priority
        rules_query = (
            select(LeadScoringRule)
            .where(
                LeadScoringRule.company_id == self.company_id,
                LeadScoringRule.is_active == True,
            )
            .order_by(LeadScoringRule.priority)
        )
        rules = list(self.session.execute(rules_query).scalars().all())

        # Apply each matching rule
        for rule in rules:
            if self._rule_matches(rule, party):
                new_score += rule.score_change
                adjustments.append(
                    ScoreAdjustment(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        rule_type=rule.rule_type,
                        score_change=rule.score_change,
                        reason=f"Matched rule: {rule.name}",
                        applied_at=datetime.utcnow(),
                    )
                )

        # Clamp score to 0-100
        new_score = max(0, min(100, new_score))

        # Update party score
        party.engagement_score = new_score
        party.updated_at = datetime.utcnow()
        self.session.flush()

        # Determine grade
        grade = self._score_to_grade(new_score)

        return LeadScoreResult(
            party_id=party_id,
            party_name=party.display_name or party.name or str(party_id),
            previous_score=previous_score,
            new_score=new_score,
            score_change=new_score - previous_score,
            adjustments=adjustments,
            grade=grade,
            qualified=new_score >= QUALIFICATION_THRESHOLD,
            calculated_at=datetime.utcnow(),
        )

    def score_all_leads(self, batch_size: int = 100) -> int:
        """Score all leads in batches."""
        # Get all parties that are leads (have lead role or party_type is lead)
        query = select(Party.id).where(
            Party.company_id == self.company_id,
            or_(
                Party.party_type == "lead",
                Party.party_type == "prospect",
            ),
        )
        party_ids = list(self.session.execute(query).scalars().all())

        scored = 0
        for party_id in party_ids:
            self.score_lead(party_id)
            scored += 1

        return scored

    def apply_decay(self) -> int:
        """Apply score decay based on rules."""
        # Get rules with decay enabled
        rules_query = select(LeadScoringRule).where(
            LeadScoringRule.company_id == self.company_id,
            LeadScoringRule.is_active == True,
            LeadScoringRule.decay_enabled == True,
        )
        rules = list(self.session.execute(rules_query).scalars().all())

        if not rules:
            return 0

        # Find max decay amount to apply
        max_decay = max(r.decay_amount for r in rules)
        if max_decay <= 0:
            return 0

        # Apply decay to parties not engaged recently
        decay_threshold = datetime.utcnow() - timedelta(days=min(r.decay_days for r in rules))

        update_query = (
            update(Party)
            .where(
                Party.company_id == self.company_id,
                Party.engagement_score > 0,
                or_(
                    Party.last_engagement_at.is_(None),
                    Party.last_engagement_at < decay_threshold,
                ),
            )
            .values(
                engagement_score=func.greatest(
                    0, Party.engagement_score - max_decay
                ),
                updated_at=datetime.utcnow(),
            )
        )
        result = self.session.execute(update_query)
        self.session.flush()

        return result.rowcount

    def _rule_matches(self, rule: LeadScoringRule, party: Party) -> bool:
        """Check if a rule's conditions match a party."""
        conditions = self._deserialize_conditions(rule.conditions)
        if not conditions:
            return True  # No conditions = always match

        for condition in conditions:
            if not self._condition_matches(condition, party):
                return False

        return True

    def _condition_matches(self, condition: ScoringCondition, party: Party) -> bool:
        """Check if a single condition matches a party."""
        field_name = condition.field
        op = condition.operator
        expected = condition.value

        # Get actual value from party
        if not hasattr(party, field_name):
            return False

        actual = getattr(party, field_name)

        # Apply operator
        if op == "equals":
            return actual == expected
        elif op == "not_equals":
            return actual != expected
        elif op == "contains":
            return expected in str(actual) if actual else False
        elif op == "gt":
            return (actual or 0) > expected
        elif op == "gte":
            return (actual or 0) >= expected
        elif op == "lt":
            return (actual or 0) < expected
        elif op == "lte":
            return (actual or 0) <= expected
        elif op == "in":
            values = expected if isinstance(expected, list) else [expected]
            return actual in values
        elif op == "not_in":
            values = expected if isinstance(expected, list) else [expected]
            return actual not in values
        elif op == "is_set":
            return actual is not None and actual != ""
        elif op == "is_not_set":
            return actual is None or actual == ""
        else:
            return False

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_rule_summary(self) -> ScoringRuleSummary:
        """Get summary of scoring rules."""
        # Count rules by type
        type_query = (
            select(
                LeadScoringRule.rule_type,
                func.count(LeadScoringRule.id).label("count"),
            )
            .where(LeadScoringRule.company_id == self.company_id)
            .group_by(LeadScoringRule.rule_type)
        )
        type_results = self.session.execute(type_query).all()
        rules_by_type = {r.rule_type: r.count for r in type_results}

        # Count rules by category
        category_query = (
            select(
                LeadScoringRule.category,
                func.count(LeadScoringRule.id).label("count"),
            )
            .where(
                LeadScoringRule.company_id == self.company_id,
                LeadScoringRule.category.isnot(None),
            )
            .group_by(LeadScoringRule.category)
        )
        category_results = self.session.execute(category_query).all()
        rules_by_category = {r.category: r.count for r in category_results}

        # Get totals
        totals_query = select(
            func.count(LeadScoringRule.id).label("total"),
            func.sum(case((LeadScoringRule.is_active == True, 1), else_=0)).label(
                "active"
            ),
            func.avg(LeadScoringRule.score_change).label("avg_change"),
        ).where(LeadScoringRule.company_id == self.company_id)
        totals = self.session.execute(totals_query).one()

        # Top scoring rules
        top_query = (
            select(LeadScoringRule)
            .where(
                LeadScoringRule.company_id == self.company_id,
                LeadScoringRule.is_active == True,
            )
            .order_by(LeadScoringRule.score_change.desc())
            .limit(5)
        )
        top_rules = list(self.session.execute(top_query).scalars().all())

        return ScoringRuleSummary(
            total_rules=totals.total or 0,
            active_rules=totals.active or 0,
            rules_by_type=rules_by_type,
            rules_by_category=rules_by_category,
            avg_score_change=float(totals.avg_change or 0),
            top_scoring_rules=[
                {
                    "id": r.id,
                    "name": r.name,
                    "score_change": r.score_change,
                    "rule_type": r.rule_type,
                }
                for r in top_rules
            ],
        )

    def get_score_distribution(self) -> ScoreDistribution:
        """Get distribution of lead scores."""
        # Get parties that are leads
        base_query = select(Party).where(
            Party.company_id == self.company_id,
            or_(
                Party.party_type == "lead",
                Party.party_type == "prospect",
            ),
        )

        # Count by grade
        grade_query = select(
            func.count(Party.id).label("total"),
            func.sum(
                case((Party.engagement_score.isnot(None), 1), else_=0)
            ).label("scored"),
            func.avg(Party.engagement_score).label("avg"),
            func.min(Party.engagement_score).label("min"),
            func.max(Party.engagement_score).label("max"),
            func.sum(
                case(
                    (Party.engagement_score >= 80, 1),
                    else_=0,
                )
            ).label("grade_a"),
            func.sum(
                case(
                    (
                        and_(
                            Party.engagement_score >= 60,
                            Party.engagement_score < 80,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("grade_b"),
            func.sum(
                case(
                    (
                        and_(
                            Party.engagement_score >= 40,
                            Party.engagement_score < 60,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("grade_c"),
            func.sum(
                case(
                    (
                        and_(
                            Party.engagement_score >= 20,
                            Party.engagement_score < 40,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("grade_d"),
            func.sum(
                case(
                    (
                        and_(
                            Party.engagement_score >= 0,
                            Party.engagement_score < 20,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("grade_f"),
            func.sum(
                case(
                    (Party.engagement_score >= QUALIFICATION_THRESHOLD, 1),
                    else_=0,
                )
            ).label("qualified"),
        ).where(
            Party.company_id == self.company_id,
            or_(
                Party.party_type == "lead",
                Party.party_type == "prospect",
            ),
        )

        result = self.session.execute(grade_query).one()

        total = result.total or 0
        scored = result.scored or 0

        return ScoreDistribution(
            total_leads=total,
            scored_leads=scored,
            unscored_leads=total - scored,
            avg_score=float(result.avg or 0),
            median_score=float(result.avg or 0),  # Simplified - would need window func for true median
            min_score=result.min or 0,
            max_score=result.max or 0,
            grade_a_count=result.grade_a or 0,
            grade_b_count=result.grade_b or 0,
            grade_c_count=result.grade_c or 0,
            grade_d_count=result.grade_d or 0,
            grade_f_count=result.grade_f or 0,
            qualified_count=result.qualified or 0,
            unqualified_count=total - (result.qualified or 0),
        )

    def get_score_history(self, party_id: int) -> Optional[ScoreHistory]:
        """Get score history for a lead."""
        party = self.session.execute(
            select(Party).where(
                Party.id == party_id, Party.company_id == self.company_id
            )
        ).scalar_one_or_none()

        if not party:
            return None

        current_score = party.engagement_score or 0
        grade = self._score_to_grade(current_score)

        # Note: For actual history, we'd need a score_history table
        # This is a simplified version
        return ScoreHistory(
            party_id=party_id,
            party_name=party.display_name or party.name or str(party_id),
            current_score=current_score,
            current_grade=grade,
            score_timeline=[],  # Would come from history table
            total_positive_adjustments=0,
            total_negative_adjustments=0,
            net_change_30d=0,
            net_change_90d=0,
            rules_applied=[],
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _score_to_grade(self, score: int) -> str:
        """Convert a numeric score to a letter grade."""
        if score >= 80:
            return "A"
        elif score >= 60:
            return "B"
        elif score >= 40:
            return "C"
        elif score >= 20:
            return "D"
        else:
            return "F"

    def _serialize_conditions(
        self, conditions: List[ScoringCondition]
    ) -> dict:
        """Serialize conditions to JSON-compatible dict."""
        return {
            "conditions": [
                {
                    "field": c.field,
                    "operator": c.operator,
                    "value": c.value,
                }
                for c in conditions
            ]
        }

    def _deserialize_conditions(
        self, data: Optional[dict]
    ) -> List[ScoringCondition]:
        """Deserialize conditions from JSON."""
        if not data or "conditions" not in data:
            return []

        return [
            ScoringCondition(
                field=c["field"],
                operator=c["operator"],
                value=c["value"],
            )
            for c in data["conditions"]
        ]
