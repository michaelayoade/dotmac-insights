"""Automation rule execution service.

Evaluates and executes automation rules when triggers fire.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.support_automation import (
    AutomationRule,
    AutomationLog,
    AutomationTrigger,
    AutomationActionType,
    ConditionOperator,
)
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.agent import Agent, Team

logger = structlog.get_logger()


class AutomationExecutor:
    """Service for executing automation rules."""

    def __init__(self, db: Session):
        self.db = db

    def execute_trigger(
        self,
        trigger: AutomationTrigger,
        ticket: Ticket,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute all matching automation rules for a trigger.

        Args:
            trigger: The trigger event that fired
            ticket: The ticket the trigger fired for
            context: Additional context (e.g., changed fields, old values)

        Returns:
            Summary of rule executions
        """
        context = context or {}
        results = {
            "trigger": trigger.value,
            "ticket_id": ticket.id,
            "rules_evaluated": 0,
            "rules_executed": 0,
            "actions_performed": 0,
            "stopped_early": False,
            "errors": [],
            "executions": [],
        }

        # Get active rules for this trigger, ordered by priority
        rules = self.db.query(AutomationRule).filter(
            AutomationRule.is_active == True,
            AutomationRule.trigger == trigger.value,
        ).order_by(AutomationRule.priority).all()

        logger.info(
            "automation_trigger_fired",
            trigger=trigger.value,
            ticket_id=ticket.id,
            rules_to_evaluate=len(rules),
        )

        for rule in rules:
            results["rules_evaluated"] += 1

            # Check rate limiting
            if not self._check_rate_limit(rule):
                logger.debug(
                    "automation_rule_rate_limited",
                    rule_id=rule.id,
                    rule_name=rule.name,
                )
                continue

            # Evaluate conditions
            start_time = time.time()
            conditions_result = self._evaluate_conditions(rule.conditions, ticket, context)

            if not conditions_result["all_matched"]:
                continue

            # Execute actions
            actions_result = self._execute_actions(rule.actions, ticket, context)
            execution_time_ms = int((time.time() - start_time) * 1000)

            results["rules_executed"] += 1
            results["actions_performed"] += actions_result["actions_executed"]

            # Log execution
            log_entry = self._log_execution(
                rule=rule,
                ticket=ticket,
                trigger=trigger,
                conditions_result=conditions_result,
                actions_result=actions_result,
                execution_time_ms=execution_time_ms,
            )

            results["executions"].append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "conditions_matched": conditions_result["matched"],
                "actions_executed": actions_result["actions_executed"],
                "success": actions_result["success"],
                "errors": actions_result["errors"],
            })

            if actions_result["errors"]:
                results["errors"].extend(actions_result["errors"])

            # Update rule stats
            rule.execution_count += 1
            rule.last_executed_at = datetime.utcnow()

            # Check if we should stop processing
            if rule.stop_processing:
                results["stopped_early"] = True
                logger.debug(
                    "automation_stop_processing",
                    rule_id=rule.id,
                    rule_name=rule.name,
                )
                break

        self.db.commit()

        logger.info(
            "automation_trigger_completed",
            trigger=trigger.value,
            ticket_id=ticket.id,
            rules_executed=results["rules_executed"],
            actions_performed=results["actions_performed"],
        )

        return results

    def _check_rate_limit(self, rule: AutomationRule) -> bool:
        """Check if rule is within rate limit."""
        if not rule.max_executions_per_hour:
            return True

        # Count executions in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_count = self.db.query(func.count(AutomationLog.id)).filter(
            AutomationLog.rule_id == rule.id,
            AutomationLog.created_at >= one_hour_ago,
        ).scalar() or 0

        return recent_count < rule.max_executions_per_hour

    def _evaluate_conditions(
        self,
        conditions: Optional[List[dict]],
        ticket: Ticket,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluate all conditions for a rule.

        Args:
            conditions: List of conditions to evaluate
            ticket: The ticket to check
            context: Additional context

        Returns:
            Evaluation results
        """
        result = {
            "all_matched": True,
            "matched": [],
            "not_matched": [],
        }

        if not conditions:
            return result

        for condition in conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "")
            value = condition.get("value")

            # Get actual value from ticket or context
            if field.startswith("context."):
                actual_value = context.get(field[8:])
            else:
                actual_value = getattr(ticket, field, None)
                if hasattr(actual_value, "value"):
                    actual_value = actual_value.value

            matched = self._check_condition(actual_value, operator, value)

            condition_info = {
                "field": field,
                "operator": operator,
                "expected": value,
                "actual": str(actual_value) if actual_value is not None else None,
                "matched": matched,
            }

            if matched:
                result["matched"].append(condition_info)
            else:
                result["not_matched"].append(condition_info)
                result["all_matched"] = False

        return result

    def _check_condition(self, actual: Any, operator: str, expected: Any) -> bool:
        """Check a single condition."""
        try:
            if operator == ConditionOperator.EQUALS.value:
                return str(actual) == str(expected)

            elif operator == ConditionOperator.NOT_EQUALS.value:
                return str(actual) != str(expected)

            elif operator == ConditionOperator.CONTAINS.value:
                return expected in str(actual or "")

            elif operator == ConditionOperator.NOT_CONTAINS.value:
                return expected not in str(actual or "")

            elif operator == ConditionOperator.STARTS_WITH.value:
                return str(actual or "").startswith(str(expected))

            elif operator == ConditionOperator.ENDS_WITH.value:
                return str(actual or "").endswith(str(expected))

            elif operator == ConditionOperator.IN_LIST.value:
                val_list = expected if isinstance(expected, list) else [expected]
                return str(actual) in [str(v) for v in val_list]

            elif operator == ConditionOperator.NOT_IN_LIST.value:
                val_list = expected if isinstance(expected, list) else [expected]
                return str(actual) not in [str(v) for v in val_list]

            elif operator == ConditionOperator.GREATER_THAN.value:
                return float(actual) > float(expected)

            elif operator == ConditionOperator.LESS_THAN.value:
                return float(actual) < float(expected)

            elif operator == ConditionOperator.GREATER_OR_EQUAL.value:
                return float(actual) >= float(expected)

            elif operator == ConditionOperator.LESS_OR_EQUAL.value:
                return float(actual) <= float(expected)

            elif operator == ConditionOperator.IS_EMPTY.value:
                return actual is None or actual == ""

            elif operator == ConditionOperator.IS_NOT_EMPTY.value:
                return actual is not None and actual != ""

            elif operator == ConditionOperator.REGEX_MATCH.value:
                try:
                    return bool(re.search(expected, str(actual or "")))
                except re.error:
                    return False

        except (TypeError, ValueError):
            return False

        return False

    def _execute_actions(
        self,
        actions: List[dict],
        ticket: Ticket,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute all actions for a rule.

        Args:
            actions: List of actions to execute
            ticket: The ticket to modify
            context: Additional context

        Returns:
            Execution results
        """
        result = {
            "success": True,
            "actions_executed": 0,
            "actions_failed": 0,
            "errors": [],
            "changes": [],
        }

        for action in actions:
            action_type = action.get("type", "")
            params = action.get("params", {})

            try:
                change = self._execute_action(action_type, params, ticket, context)
                if change:
                    result["changes"].append(change)
                    result["actions_executed"] += 1
            except Exception as e:
                result["actions_failed"] += 1
                result["errors"].append(f"Action {action_type} failed: {str(e)}")
                logger.error(
                    "automation_action_failed",
                    action_type=action_type,
                    ticket_id=ticket.id,
                    error=str(e),
                )

        if result["actions_failed"] > 0:
            result["success"] = False

        return result

    def _execute_action(
        self,
        action_type: str,
        params: dict,
        ticket: Ticket,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Execute a single action.

        Args:
            action_type: Type of action
            params: Action parameters
            ticket: Ticket to modify
            context: Additional context

        Returns:
            Description of change made, or None
        """
        if action_type == AutomationActionType.SET_PRIORITY.value:
            old_value = ticket.priority.value if ticket.priority else None
            new_value = params.get("priority")
            try:
                ticket.priority = TicketPriority(new_value)
                return {
                    "action": "set_priority",
                    "old": old_value,
                    "new": new_value,
                }
            except ValueError:
                raise ValueError(f"Invalid priority: {new_value}")

        elif action_type == AutomationActionType.SET_STATUS.value:
            old_value = ticket.status.value if ticket.status else None
            new_value = params.get("status")
            try:
                ticket.status = TicketStatus(new_value)
                return {
                    "action": "set_status",
                    "old": old_value,
                    "new": new_value,
                }
            except ValueError:
                raise ValueError(f"Invalid status: {new_value}")

        elif action_type == AutomationActionType.ASSIGN_AGENT.value:
            old_value = ticket.assigned_to
            agent_id = params.get("agent_id")
            agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                raise ValueError(f"Agent not found: {agent_id}")
            ticket.assigned_to = agent.display_name or agent.email
            return {
                "action": "assign_agent",
                "old": old_value,
                "new": ticket.assigned_to,
                "agent_id": agent_id,
            }

        elif action_type == AutomationActionType.ASSIGN_TEAM.value:
            old_value = ticket.team_id
            team_id = params.get("team_id")
            team = self.db.query(Team).filter(Team.id == team_id).first()
            if not team:
                raise ValueError(f"Team not found: {team_id}")
            ticket.team_id = team_id
            return {
                "action": "assign_team",
                "old": old_value,
                "new": team_id,
                "team_name": team.name,
            }

        elif action_type == AutomationActionType.ADD_TAG.value:
            tag = params.get("tag")
            if tag:
                tags = ticket.tags or []
                if isinstance(tags, list) and tag not in tags:
                    tags.append(tag)
                    ticket.tags = tags
                    return {"action": "add_tag", "tag": tag}

        elif action_type == AutomationActionType.REMOVE_TAG.value:
            tag = params.get("tag")
            if tag:
                tags = ticket.tags or []
                if isinstance(tags, list) and tag in tags:
                    tags.remove(tag)
                    ticket.tags = tags
                    return {"action": "remove_tag", "tag": tag}

        elif action_type == AutomationActionType.UPDATE_FIELD.value:
            field = params.get("field")
            value = params.get("value")
            if field and hasattr(ticket, field):
                old_value = getattr(ticket, field)
                setattr(ticket, field, value)
                return {
                    "action": "update_field",
                    "field": field,
                    "old": str(old_value) if old_value else None,
                    "new": str(value),
                }

        elif action_type == AutomationActionType.ADD_COMMENT.value:
            # This would need to create a TicketComment
            # For now, log intention
            content = params.get("content", "")
            logger.info(
                "automation_add_comment",
                ticket_id=ticket.id,
                content_preview=content[:100],
            )
            return {"action": "add_comment", "content_length": len(content)}

        elif action_type == AutomationActionType.SEND_NOTIFICATION.value:
            # Queue notification (would integrate with notification service)
            recipients = params.get("recipients", [])
            message = params.get("message", "")
            logger.info(
                "automation_send_notification",
                ticket_id=ticket.id,
                recipients=recipients,
            )
            return {"action": "send_notification", "recipients": recipients}

        elif action_type == AutomationActionType.SEND_EMAIL.value:
            # Queue email (would integrate with email service)
            to = params.get("to", "")
            subject = params.get("subject", "")
            logger.info(
                "automation_send_email",
                ticket_id=ticket.id,
                to=to,
                subject=subject,
            )
            return {"action": "send_email", "to": to, "subject": subject}

        elif action_type == AutomationActionType.ESCALATE.value:
            # Mark as escalated and optionally assign
            ticket.is_escalated = True
            escalate_to = params.get("escalate_to")
            if escalate_to:
                ticket.assigned_to = escalate_to
            return {"action": "escalate", "escalate_to": escalate_to}

        elif action_type == AutomationActionType.WEBHOOK.value:
            # Log webhook trigger (actual sending would be async)
            url = params.get("url", "")
            logger.info(
                "automation_webhook_triggered",
                ticket_id=ticket.id,
                url=url,
            )
            return {"action": "webhook", "url": url}

        return None

    def _log_execution(
        self,
        rule: AutomationRule,
        ticket: Ticket,
        trigger: AutomationTrigger,
        conditions_result: Dict[str, Any],
        actions_result: Dict[str, Any],
        execution_time_ms: int,
    ) -> AutomationLog:
        """Log an automation execution."""
        log = AutomationLog(
            rule_id=rule.id,
            ticket_id=ticket.id,
            trigger=trigger.value,
            conditions_matched=conditions_result["matched"],
            actions_executed=actions_result["changes"],
            success=actions_result["success"],
            error_message="; ".join(actions_result["errors"]) if actions_result["errors"] else None,
            execution_time_ms=execution_time_ms,
        )
        self.db.add(log)
        return log

    def test_rule(
        self,
        rule: AutomationRule,
        ticket: Ticket,
    ) -> Dict[str, Any]:
        """Test a rule against a ticket without executing actions.

        Args:
            rule: Rule to test
            ticket: Ticket to test against

        Returns:
            What would happen if rule executed
        """
        conditions_result = self._evaluate_conditions(rule.conditions, ticket, {})

        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "ticket_id": ticket.id,
            "would_trigger": conditions_result["all_matched"],
            "conditions": {
                "matched": conditions_result["matched"],
                "not_matched": conditions_result["not_matched"],
            },
            "actions_would_execute": rule.actions if conditions_result["all_matched"] else [],
        }

    def find_idle_tickets(
        self,
        idle_hours: int = 24,
        limit: int = 100,
    ) -> List[Ticket]:
        """Find tickets that have been idle.

        Args:
            idle_hours: Hours since last update to consider idle
            limit: Maximum tickets to return

        Returns:
            List of idle tickets
        """
        threshold = datetime.utcnow() - timedelta(hours=idle_hours)

        return self.db.query(Ticket).filter(
            Ticket.status.in_([
                TicketStatus.OPEN,
                TicketStatus.IN_PROGRESS,
                TicketStatus.PENDING,
            ]),
            Ticket.updated_at < threshold,
        ).order_by(Ticket.updated_at).limit(limit).all()

    def process_idle_tickets(self, idle_hours: int = 24) -> Dict[str, Any]:
        """Process idle tickets with automation.

        Args:
            idle_hours: Hours threshold for idle

        Returns:
            Processing summary
        """
        tickets = self.find_idle_tickets(idle_hours)

        results = {
            "idle_tickets_found": len(tickets),
            "automations_triggered": 0,
            "details": [],
        }

        for ticket in tickets:
            result = self.execute_trigger(
                AutomationTrigger.TICKET_IDLE,
                ticket,
                {"idle_hours": idle_hours},
            )
            if result["rules_executed"] > 0:
                results["automations_triggered"] += 1
            results["details"].append({
                "ticket_id": ticket.id,
                "rules_executed": result["rules_executed"],
            })

        logger.info(
            "idle_tickets_processed",
            found=results["idle_tickets_found"],
            triggered=results["automations_triggered"],
        )

        return results
