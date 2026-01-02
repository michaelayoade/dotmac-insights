"""Automation service - business logic for automation rules and triggers.

This service handles automation execution:
- Trigger-based rule matching
- Condition evaluation
- Action execution

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.omni import OmniConversation
from app.models.ticket import Ticket

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["AutomationService", "AutomationRule", "ActionResult", "ExecutionLog"]


@dataclass
class AutomationRule:
    """An automation rule definition."""

    id: str
    name: str
    trigger: str  # on_create, on_update, on_status_change, scheduled
    entity_type: str  # ticket, conversation
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    is_active: bool = True
    priority: int = 0


@dataclass
class ActionResult:
    """Result of executing an automation action."""

    action_type: str
    success: bool
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionLog:
    """Log of an automation rule execution."""

    rule_id: str
    rule_name: str
    trigger: str
    entity_type: str
    entity_id: int
    matched: bool
    actions_executed: List[ActionResult] = field(default_factory=list)
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AutomationService:
    """Service for automation rule execution.

    This service evaluates and executes automation rules based on triggers.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal
        self._rules: List[AutomationRule] = []
        self._action_handlers: Dict[str, Callable] = {}

        # Register default action handlers
        self._register_default_handlers()

    # -------------------------------------------------------------------------
    # Rule Management (in-memory for now, can be DB-backed later)
    # -------------------------------------------------------------------------

    def register_rule(self, rule: AutomationRule) -> None:
        """Register an automation rule."""
        self._rules.append(rule)

    def unregister_rule(self, rule_id: str) -> bool:
        """Unregister an automation rule."""
        for i, rule in enumerate(self._rules):
            if rule.id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def get_rules(
        self,
        trigger: Optional[str] = None,
        entity_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[AutomationRule]:
        """Get automation rules with optional filtering."""
        rules = self._rules

        if active_only:
            rules = [r for r in rules if r.is_active]

        if trigger:
            rules = [r for r in rules if r.trigger == trigger]

        if entity_type:
            rules = [r for r in rules if r.entity_type == entity_type]

        return sorted(rules, key=lambda r: r.priority, reverse=True)

    # -------------------------------------------------------------------------
    # Action Handler Registration
    # -------------------------------------------------------------------------

    def register_action_handler(
        self,
        action_type: str,
        handler: Callable[[Any, Dict[str, Any]], ActionResult],
    ) -> None:
        """Register a handler for an action type."""
        self._action_handlers[action_type] = handler

    def _register_default_handlers(self) -> None:
        """Register default action handlers."""
        self.register_action_handler("update_status", self._handle_update_status)
        self.register_action_handler("update_priority", self._handle_update_priority)
        self.register_action_handler("add_tag", self._handle_add_tag)
        self.register_action_handler("remove_tag", self._handle_remove_tag)
        self.register_action_handler("assign_agent", self._handle_assign_agent)
        self.register_action_handler("assign_team", self._handle_assign_team)
        self.register_action_handler("send_notification", self._handle_send_notification)

    # -------------------------------------------------------------------------
    # Trigger Execution
    # -------------------------------------------------------------------------

    def execute_for_trigger(
        self,
        trigger: str,
        entity: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ExecutionLog]:
        """Execute automation rules for a trigger.

        Args:
            trigger: The trigger type (on_create, on_update, etc.)
            entity: The entity that triggered the automation.
            context: Additional context data.

        Returns:
            List of execution logs.
        """
        entity_type = self._get_entity_type(entity)
        rules = self.get_rules(trigger=trigger, entity_type=entity_type)

        logs = []
        for rule in rules:
            log = self._execute_rule(rule, entity, context or {})
            logs.append(log)

        return logs

    def _execute_rule(
        self,
        rule: AutomationRule,
        entity: Any,
        context: Dict[str, Any],
    ) -> ExecutionLog:
        """Execute a single automation rule."""
        entity_id = getattr(entity, "id", 0)

        # Check if conditions match
        matched = self.evaluate_rule(rule, entity, context)

        log = ExecutionLog(
            rule_id=rule.id,
            rule_name=rule.name,
            trigger=rule.trigger,
            entity_type=rule.entity_type,
            entity_id=entity_id,
            matched=matched,
        )

        if not matched:
            return log

        # Execute actions
        for action in rule.actions:
            result = self.execute_action(action, entity, context)
            log.actions_executed.append(result)

        return log

    # -------------------------------------------------------------------------
    # Condition Evaluation
    # -------------------------------------------------------------------------

    def evaluate_rule(
        self,
        rule: AutomationRule,
        entity: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Evaluate if a rule's conditions match the entity.

        Args:
            rule: The automation rule.
            entity: The entity to evaluate against.
            context: Additional context data.

        Returns:
            True if all conditions match, False otherwise.
        """
        if not rule.conditions:
            return True  # No conditions = always match

        for condition in rule.conditions:
            if not self._evaluate_condition(condition, entity, context or {}):
                return False

        return True

    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        entity: Any,
        context: Dict[str, Any],
    ) -> bool:
        """Evaluate a single condition."""
        cond_type = condition.get("type")
        field = condition.get("field")
        operator = condition.get("operator", "equals")
        value = condition.get("value")

        # Get the actual value from entity
        if field:
            actual = getattr(entity, field, None)
            if hasattr(actual, "value"):  # Handle enums
                actual = actual.value
        else:
            actual = None

        # Evaluate based on operator
        if operator == "equals":
            return actual == value
        elif operator == "not_equals":
            return actual != value
        elif operator == "contains":
            return value in (actual or "")
        elif operator == "not_contains":
            return value not in (actual or "")
        elif operator == "in":
            return actual in (value if isinstance(value, list) else [value])
        elif operator == "not_in":
            return actual not in (value if isinstance(value, list) else [value])
        elif operator == "greater_than":
            return (actual or 0) > value
        elif operator == "less_than":
            return (actual or 0) < value
        elif operator == "is_empty":
            return not actual
        elif operator == "is_not_empty":
            return bool(actual)

        return False

    # -------------------------------------------------------------------------
    # Action Execution
    # -------------------------------------------------------------------------

    def execute_action(
        self,
        action: Dict[str, Any],
        entity: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Execute a single automation action.

        Args:
            action: Action configuration.
            entity: The entity to act on.
            context: Additional context data.

        Returns:
            ActionResult with outcome.
        """
        action_type = action.get("type", "unknown")
        handler = self._action_handlers.get(action_type)

        if not handler:
            return ActionResult(
                action_type=action_type,
                success=False,
                message=f"Unknown action type: {action_type}",
            )

        try:
            return handler(entity, action)
        except Exception as e:
            return ActionResult(
                action_type=action_type,
                success=False,
                message=str(e),
            )

    # -------------------------------------------------------------------------
    # Default Action Handlers
    # -------------------------------------------------------------------------

    def _handle_update_status(
        self,
        entity: Any,
        action: Dict[str, Any],
    ) -> ActionResult:
        """Handle update_status action."""
        new_status = action.get("value")
        if not new_status:
            return ActionResult(
                action_type="update_status",
                success=False,
                message="No status value provided",
            )

        if hasattr(entity, "status"):
            entity.status = new_status
            self.db.flush()
            return ActionResult(
                action_type="update_status",
                success=True,
                message=f"Status updated to {new_status}",
            )

        return ActionResult(
            action_type="update_status",
            success=False,
            message="Entity has no status field",
        )

    def _handle_update_priority(
        self,
        entity: Any,
        action: Dict[str, Any],
    ) -> ActionResult:
        """Handle update_priority action."""
        new_priority = action.get("value")
        if not new_priority:
            return ActionResult(
                action_type="update_priority",
                success=False,
                message="No priority value provided",
            )

        if hasattr(entity, "priority"):
            entity.priority = new_priority
            self.db.flush()
            return ActionResult(
                action_type="update_priority",
                success=True,
                message=f"Priority updated to {new_priority}",
            )

        return ActionResult(
            action_type="update_priority",
            success=False,
            message="Entity has no priority field",
        )

    def _handle_add_tag(
        self,
        entity: Any,
        action: Dict[str, Any],
    ) -> ActionResult:
        """Handle add_tag action."""
        tag = action.get("value")
        if not tag:
            return ActionResult(
                action_type="add_tag",
                success=False,
                message="No tag value provided",
            )

        if hasattr(entity, "tags"):
            current_tags = list(entity.tags or [])
            if tag not in current_tags:
                current_tags.append(tag)
                entity.tags = current_tags
                self.db.flush()
            return ActionResult(
                action_type="add_tag",
                success=True,
                message=f"Tag '{tag}' added",
            )

        return ActionResult(
            action_type="add_tag",
            success=False,
            message="Entity has no tags field",
        )

    def _handle_remove_tag(
        self,
        entity: Any,
        action: Dict[str, Any],
    ) -> ActionResult:
        """Handle remove_tag action."""
        tag = action.get("value")
        if not tag:
            return ActionResult(
                action_type="remove_tag",
                success=False,
                message="No tag value provided",
            )

        if hasattr(entity, "tags"):
            current_tags = list(entity.tags or [])
            if tag in current_tags:
                current_tags.remove(tag)
                entity.tags = current_tags if current_tags else None
                self.db.flush()
            return ActionResult(
                action_type="remove_tag",
                success=True,
                message=f"Tag '{tag}' removed",
            )

        return ActionResult(
            action_type="remove_tag",
            success=False,
            message="Entity has no tags field",
        )

    def _handle_assign_agent(
        self,
        entity: Any,
        action: Dict[str, Any],
    ) -> ActionResult:
        """Handle assign_agent action."""
        agent_id = action.get("value")
        if not agent_id:
            return ActionResult(
                action_type="assign_agent",
                success=False,
                message="No agent_id provided",
            )

        if hasattr(entity, "assigned_agent_id"):
            entity.assigned_agent_id = int(agent_id)
            if hasattr(entity, "assigned_at"):
                entity.assigned_at = datetime.now(timezone.utc)
            self.db.flush()
            return ActionResult(
                action_type="assign_agent",
                success=True,
                message=f"Assigned to agent {agent_id}",
            )

        return ActionResult(
            action_type="assign_agent",
            success=False,
            message="Entity has no assigned_agent_id field",
        )

    def _handle_assign_team(
        self,
        entity: Any,
        action: Dict[str, Any],
    ) -> ActionResult:
        """Handle assign_team action."""
        team_id = action.get("value")
        if not team_id:
            return ActionResult(
                action_type="assign_team",
                success=False,
                message="No team_id provided",
            )

        if hasattr(entity, "assigned_team_id"):
            entity.assigned_team_id = int(team_id)
            if hasattr(entity, "assigned_at"):
                entity.assigned_at = datetime.now(timezone.utc)
            self.db.flush()
            return ActionResult(
                action_type="assign_team",
                success=True,
                message=f"Assigned to team {team_id}",
            )

        return ActionResult(
            action_type="assign_team",
            success=False,
            message="Entity has no assigned_team_id field",
        )

    def _handle_send_notification(
        self,
        entity: Any,
        action: Dict[str, Any],
    ) -> ActionResult:
        """Handle send_notification action."""
        # TODO: Implement actual notification sending
        return ActionResult(
            action_type="send_notification",
            success=True,
            message="Notification sending not yet implemented",
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_entity_type(self, entity: Any) -> str:
        """Determine the entity type from the entity."""
        if isinstance(entity, Ticket):
            return "ticket"
        elif isinstance(entity, OmniConversation):
            return "conversation"
        else:
            return "unknown"
