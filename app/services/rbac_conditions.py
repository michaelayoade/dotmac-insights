"""RBAC Condition Evaluator - Evaluates conditional permissions.

Supports various condition types:
- own_only: User owns the resource (user_id == resource_owner_id)
- department_id: User is in one of the specified departments
- time_range: Current time is within the specified range
- ip_range: Client IP is within the specified CIDR range
- resource fields: Arbitrary resource field comparisons

Condition Format (JSON):
{
    "type": "and" | "or",
    "conditions": [
        {"field": "own_only", "value": true},
        {"field": "department_id", "operator": "in", "values": [1, 2, 3]},
        {"field": "time_range", "start": "09:00", "end": "17:00", "timezone": "Africa/Lagos"},
        {"field": "ip_range", "operator": "cidr", "value": "192.168.1.0/24"},
        {"field": "resource.amount", "operator": "lte", "value": 100000}
    ]
}
"""

from __future__ import annotations

import ipaddress
from datetime import datetime, time
from typing import Any, Optional

import structlog
from pydantic import BaseModel

from app.utils.datetime_utils import utc_now

logger = structlog.get_logger()


class PermissionContext(BaseModel):
    """Context for evaluating conditional permissions."""

    user_id: int
    resource_owner_id: Optional[int] = None
    department_id: Optional[int] = None
    department_ids: list[int] = []  # All departments user belongs to
    current_time: datetime = None
    client_ip: Optional[str] = None
    resource: Optional[dict] = None  # The resource being accessed
    request_path: Optional[str] = None
    request_method: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        if data.get("current_time") is None:
            data["current_time"] = utc_now()
        super().__init__(**data)


class ConditionEvaluator:
    """Evaluates JSON-based permission conditions."""

    # Supported operators for comparisons
    OPERATORS = {
        "eq": lambda a, b: a == b,
        "ne": lambda a, b: a != b,
        "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "in": lambda a, b: a in b,
        "not_in": lambda a, b: a not in b,
        "contains": lambda a, b: b in a if a else False,
        "starts_with": lambda a, b: a.startswith(b) if a else False,
        "ends_with": lambda a, b: a.endswith(b) if a else False,
        "cidr": lambda ip, cidr: ConditionEvaluator._check_cidr(ip, cidr),
    }

    def evaluate(
        self,
        conditions: dict,
        context: PermissionContext,
    ) -> bool:
        """
        Evaluate conditions against the given context.

        Args:
            conditions: JSON condition object
            context: Permission context with user, resource, etc.

        Returns:
            True if conditions are satisfied
        """
        if not conditions:
            return True

        # Handle simple conditions (single condition without wrapper)
        if "field" in conditions:
            return self._evaluate_single(conditions, context)

        condition_type = conditions.get("type", "and")
        sub_conditions = conditions.get("conditions", [])

        if not sub_conditions:
            return True

        results = [self._evaluate_single(c, context) for c in sub_conditions]

        if condition_type == "and":
            return all(results)
        elif condition_type == "or":
            return any(results)
        else:
            logger.warning("unknown_condition_type", type=condition_type)
            return False

    def _evaluate_single(
        self,
        condition: dict,
        context: PermissionContext,
    ) -> bool:
        """Evaluate a single condition."""
        field = condition.get("field")

        if not field:
            return True

        try:
            # Handle special condition types
            if field == "own_only":
                return self._evaluate_own_only(condition, context)
            elif field == "department_id":
                return self._evaluate_department(condition, context)
            elif field == "time_range":
                return self._evaluate_time_range(condition, context)
            elif field == "ip_range":
                return self._evaluate_ip_range(condition, context)
            elif field.startswith("resource."):
                return self._evaluate_resource_field(condition, context)
            elif field.startswith("request."):
                return self._evaluate_request_field(condition, context)
            else:
                logger.error("unknown_condition_field", field=field)
                return False  # Unknown conditions fail closed - deny access

        except Exception as e:
            logger.error("condition_evaluation_error", field=field, error=str(e))
            return False

    def _evaluate_own_only(
        self,
        condition: dict,
        context: PermissionContext,
    ) -> bool:
        """Check if user owns the resource."""
        value = condition.get("value", True)
        if not value:
            return True  # own_only: false means no restriction

        if context.resource_owner_id is None:
            # No owner specified - fail closed since we can't verify ownership
            logger.warning("own_only_check_missing_owner", user_id=context.user_id)
            return False

        return context.user_id == context.resource_owner_id

    def _evaluate_department(
        self,
        condition: dict,
        context: PermissionContext,
    ) -> bool:
        """Check if user is in one of the allowed departments."""
        operator = condition.get("operator", "in")
        allowed_ids = condition.get("values", [])

        if not allowed_ids:
            return True

        # Check against user's department(s)
        user_depts = set(context.department_ids)
        if context.department_id:
            user_depts.add(context.department_id)

        if operator == "in":
            return bool(user_depts & set(allowed_ids))
        elif operator == "not_in":
            return not bool(user_depts & set(allowed_ids))

        return False

    def _evaluate_time_range(
        self,
        condition: dict,
        context: PermissionContext,
    ) -> bool:
        """Check if current time is within the allowed range."""
        start_str = condition.get("start")
        end_str = condition.get("end")
        timezone_str = condition.get("timezone", "UTC")
        days = condition.get("days")  # Optional: [0, 1, 2, 3, 4] = Mon-Fri

        if not start_str or not end_str:
            return True

        try:
            # Parse time strings
            start_time = time.fromisoformat(start_str)
            end_time = time.fromisoformat(end_str)

            # Get current time in the specified timezone
            # For simplicity, we'll use UTC comparison
            # A full implementation would convert to the specified timezone
            current = context.current_time
            current_time = current.time()
            current_day = current.weekday()

            # Check day restriction
            if days is not None and current_day not in days:
                return False

            # Check time range
            if start_time <= end_time:
                # Normal range (e.g., 09:00 to 17:00)
                return start_time <= current_time <= end_time
            else:
                # Overnight range (e.g., 22:00 to 06:00)
                return current_time >= start_time or current_time <= end_time

        except ValueError as e:
            logger.warning("invalid_time_range", error=str(e))
            return True

    def _evaluate_ip_range(
        self,
        condition: dict,
        context: PermissionContext,
    ) -> bool:
        """Check if client IP is within the allowed range."""
        cidr = condition.get("value")
        operator = condition.get("operator", "cidr")

        if not cidr or not context.client_ip:
            return True

        if operator == "cidr":
            return self._check_cidr(context.client_ip, cidr)
        elif operator == "eq":
            return context.client_ip == cidr

        return True

    @staticmethod
    def _check_cidr(ip_str: str, cidr: str) -> bool:
        """Check if IP is within CIDR range."""
        try:
            ip = ipaddress.ip_address(ip_str)
            network = ipaddress.ip_network(cidr, strict=False)
            return ip in network
        except ValueError:
            return False

    def _evaluate_resource_field(
        self,
        condition: dict,
        context: PermissionContext,
    ) -> bool:
        """Evaluate a condition on a resource field."""
        field = condition.get("field", "")
        operator = condition.get("operator", "eq")
        expected_value = condition.get("value")
        expected_values = condition.get("values", [])

        if not context.resource:
            # Resource required but not provided - fail closed
            logger.warning("resource_field_check_missing_resource", field=field)
            return False

        # Extract field path (e.g., "resource.amount" -> "amount")
        field_path = field.replace("resource.", "", 1)
        actual_value = self._get_nested_value(context.resource, field_path)

        if actual_value is None:
            # Field doesn't exist on resource - fail closed
            logger.warning("resource_field_not_found", field=field_path)
            return False

        # Get the comparison function
        compare_fn = self.OPERATORS.get(operator)
        if not compare_fn:
            logger.error("unknown_operator", operator=operator)
            return False  # Unknown operator - fail closed

        # Use values array for in/not_in operators
        if operator in ("in", "not_in"):
            return compare_fn(actual_value, expected_values)

        return compare_fn(actual_value, expected_value)

    def _evaluate_request_field(
        self,
        condition: dict,
        context: PermissionContext,
    ) -> bool:
        """Evaluate a condition on request properties."""
        field = condition.get("field", "")
        operator = condition.get("operator", "eq")
        expected_value = condition.get("value")

        field_name = field.replace("request.", "", 1)

        if field_name == "method":
            actual_value = context.request_method
        elif field_name == "path":
            actual_value = context.request_path
        else:
            return True

        if actual_value is None:
            return True

        compare_fn = self.OPERATORS.get(operator)
        if not compare_fn:
            return True

        return compare_fn(actual_value, expected_value)

    def _get_nested_value(self, obj: dict, path: str) -> Any:
        """Get a nested value from a dict using dot notation."""
        keys = path.split(".")
        current = obj

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None

            if current is None:
                return None

        return current


# Singleton instance
condition_evaluator = ConditionEvaluator()


def evaluate_conditions(conditions: dict, context: PermissionContext) -> bool:
    """Convenience function to evaluate conditions."""
    return condition_evaluator.evaluate(conditions, context)
