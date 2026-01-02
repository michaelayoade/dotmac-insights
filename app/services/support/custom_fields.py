"""Custom field service - business logic for dynamic ticket fields.

This service handles custom field configuration:
- CRUD operations for custom ticket fields
- Field validation
- Field value management
- Conditional field logic

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.support_settings import TicketFieldConfig

from .types import (
    CustomFieldCreate,
    CustomFieldUpdate,
)
from .errors import (
    CustomFieldNotFoundError,
    DuplicateFieldKeyError,
    ValidationError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["CustomFieldService"]

# Valid field types
FIELD_TYPES = [
    "TEXT",
    "NUMBER",
    "DROPDOWN",
    "MULTISELECT",
    "DATE",
    "DATETIME",
    "CHECKBOX",
    "URL",
    "EMAIL",
    "TEXTAREA",
]


class CustomFieldService:
    """Service for custom ticket field management.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list(
        self,
        active_only: bool = True,
        ticket_type: Optional[str] = None,
        show_in_list: Optional[bool] = None,
        show_in_create_form: Optional[bool] = None,
        show_in_customer_portal: Optional[bool] = None,
        company: Optional[str] = None,
    ) -> List[TicketFieldConfig]:
        """List custom fields with optional filtering.

        Args:
            active_only: Only return active fields.
            ticket_type: Filter by applicable ticket type.
            show_in_list: Filter by list visibility.
            show_in_create_form: Filter by create form visibility.
            show_in_customer_portal: Filter by portal visibility.
            company: Filter by company.

        Returns:
            List of TicketFieldConfig instances.
        """
        query = self.db.query(TicketFieldConfig)

        if company:
            query = query.filter(
                or_(TicketFieldConfig.company == company, TicketFieldConfig.company.is_(None))
            )

        if active_only:
            query = query.filter(TicketFieldConfig.is_active == True)

        if show_in_list is not None:
            query = query.filter(TicketFieldConfig.show_in_list == show_in_list)

        if show_in_create_form is not None:
            query = query.filter(TicketFieldConfig.show_in_create_form == show_in_create_form)

        if show_in_customer_portal is not None:
            query = query.filter(TicketFieldConfig.show_in_customer_portal == show_in_customer_portal)

        fields = query.order_by(TicketFieldConfig.display_order.asc()).all()

        # Filter by ticket type if specified (requires JSON field check)
        if ticket_type:
            fields = [
                f for f in fields
                if f.applies_to_types is None or ticket_type in f.applies_to_types
            ]

        return fields

    def get(self, field_id: int) -> TicketFieldConfig:
        """Get a custom field by ID.

        Args:
            field_id: The field ID.

        Returns:
            TicketFieldConfig instance.

        Raises:
            CustomFieldNotFoundError: If not found.
        """
        field = (
            self.db.query(TicketFieldConfig)
            .filter(TicketFieldConfig.id == field_id)
            .first()
        )
        if not field:
            raise CustomFieldNotFoundError(field_id)
        return field

    def get_by_key(self, field_key: str, company: Optional[str] = None) -> Optional[TicketFieldConfig]:
        """Get a custom field by key.

        Args:
            field_key: The field key.
            company: Optional company filter.

        Returns:
            TicketFieldConfig instance or None.
        """
        query = self.db.query(TicketFieldConfig).filter(TicketFieldConfig.field_key == field_key)
        if company:
            query = query.filter(
                or_(TicketFieldConfig.company == company, TicketFieldConfig.company.is_(None))
            )
        return query.first()

    def get_required_fields(
        self,
        ticket_type: Optional[str] = None,
        company: Optional[str] = None,
    ) -> List[TicketFieldConfig]:
        """Get required custom fields.

        Args:
            ticket_type: Filter by applicable ticket type.
            company: Filter by company.

        Returns:
            List of required TicketFieldConfig instances.
        """
        fields = self.list(
            active_only=True,
            ticket_type=ticket_type,
            company=company,
        )
        return [f for f in fields if f.is_required]

    def get_form_fields(
        self,
        ticket_type: Optional[str] = None,
        for_portal: bool = False,
        company: Optional[str] = None,
    ) -> List[TicketFieldConfig]:
        """Get fields for a ticket form.

        Args:
            ticket_type: Filter by applicable ticket type.
            for_portal: If True, only return portal-visible fields.
            company: Filter by company.

        Returns:
            List of TicketFieldConfig instances for the form.
        """
        if for_portal:
            return self.list(
                active_only=True,
                ticket_type=ticket_type,
                show_in_customer_portal=True,
                company=company,
            )
        else:
            return self.list(
                active_only=True,
                ticket_type=ticket_type,
                show_in_create_form=True,
                company=company,
            )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create(self, data: CustomFieldCreate, company: Optional[str] = None) -> TicketFieldConfig:
        """Create a new custom field.

        Args:
            data: Field creation data.
            company: Optional company scope.

        Returns:
            Created TicketFieldConfig instance.

        Raises:
            DuplicateFieldKeyError: If field_key already exists.
            ValidationError: If field type is invalid.
        """
        # Validate field type
        field_type = data.field_type.upper()
        if field_type not in FIELD_TYPES:
            raise ValidationError(f"Invalid field type: {data.field_type}. Must be one of: {', '.join(FIELD_TYPES)}")

        # Check for duplicate key
        existing = self.get_by_key(data.field_key, company)
        if existing:
            raise DuplicateFieldKeyError(data.field_key)

        # Validate field key format (alphanumeric + underscore)
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', data.field_key):
            raise ValidationError(
                "Field key must start with a letter and contain only letters, numbers, and underscores"
            )

        field = TicketFieldConfig(
            company=company,
            field_name=data.name,
            field_key=data.field_key,
            field_type=field_type,
            options=data.options,
            is_required=data.is_required,
            min_length=data.min_length,
            max_length=data.max_length,
            validation_regex=data.validation_regex,
            default_value=data.default_value,
            display_order=data.display_order,
            show_in_list=data.show_in_list,
            show_in_create_form=data.show_in_create_form,
            show_in_customer_portal=data.show_in_customer_portal,
            applies_to_types=data.applies_to_types,
            is_active=True,
        )

        self.db.add(field)
        self.db.flush()
        return field

    def update(self, field_id: int, data: CustomFieldUpdate) -> TicketFieldConfig:
        """Update a custom field.

        Args:
            field_id: The field ID.
            data: Update data.

        Returns:
            Updated TicketFieldConfig instance.

        Raises:
            CustomFieldNotFoundError: If not found.
        """
        field = self.get(field_id)

        if data.name is not None:
            field.field_name = data.name

        if data.description is not None:
            # Note: TicketFieldConfig doesn't have description, but we can store in options
            pass

        if data.options is not None:
            field.options = data.options

        if data.default_value is not None:
            field.default_value = data.default_value

        if data.is_required is not None:
            field.is_required = data.is_required

        if data.min_length is not None:
            field.min_length = data.min_length

        if data.max_length is not None:
            field.max_length = data.max_length

        if data.validation_regex is not None:
            field.validation_regex = data.validation_regex

        if data.display_order is not None:
            field.display_order = data.display_order

        if data.show_in_list is not None:
            field.show_in_list = data.show_in_list

        if data.show_in_create_form is not None:
            field.show_in_create_form = data.show_in_create_form

        if data.show_in_customer_portal is not None:
            field.show_in_customer_portal = data.show_in_customer_portal

        if data.applies_to_types is not None:
            field.applies_to_types = data.applies_to_types

        if data.is_active is not None:
            field.is_active = data.is_active

        self.db.flush()
        return field

    def delete(self, field_id: int) -> bool:
        """Delete a custom field.

        Args:
            field_id: The field ID.

        Returns:
            True if deleted.

        Raises:
            CustomFieldNotFoundError: If not found.
        """
        field = self.get(field_id)
        self.db.delete(field)
        self.db.flush()
        return True

    def reorder(self, field_ids: List[int]) -> List[TicketFieldConfig]:
        """Reorder fields by setting display_order.

        Args:
            field_ids: List of field IDs in desired order.

        Returns:
            List of updated TicketFieldConfig instances.
        """
        fields = []
        for order, field_id in enumerate(field_ids):
            try:
                field = self.get(field_id)
                field.display_order = order
                fields.append(field)
            except CustomFieldNotFoundError:
                continue

        self.db.flush()
        return fields

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate_value(
        self,
        field_id: int,
        value: Any,
    ) -> tuple[bool, Optional[str]]:
        """Validate a value against a custom field's rules.

        Args:
            field_id: The field ID.
            value: The value to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        field = self.get(field_id)
        return self._validate_field_value(field, value)

    def validate_values(
        self,
        values: Dict[str, Any],
        ticket_type: Optional[str] = None,
        company: Optional[str] = None,
    ) -> tuple[bool, Dict[str, str]]:
        """Validate multiple custom field values.

        Args:
            values: Dict of field_key -> value.
            ticket_type: Filter by applicable ticket type.
            company: Filter by company.

        Returns:
            Tuple of (all_valid, errors_dict).
        """
        fields = self.list(active_only=True, ticket_type=ticket_type, company=company)
        errors = {}

        for field in fields:
            value = values.get(field.field_key)

            # Check required fields
            if field.is_required and (value is None or value == ""):
                errors[field.field_key] = f"{field.field_name} is required"
                continue

            # Skip validation if value is empty and not required
            if value is None or value == "":
                continue

            is_valid, error = self._validate_field_value(field, value)
            if not is_valid:
                errors[field.field_key] = error

        return len(errors) == 0, errors

    def _validate_field_value(
        self,
        field: TicketFieldConfig,
        value: Any,
    ) -> tuple[bool, Optional[str]]:
        """Validate a value against a field's rules.

        Args:
            field: The field configuration.
            value: The value to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        field_type = field.field_type.upper()

        # Type-specific validation
        if field_type == "TEXT" or field_type == "TEXTAREA":
            if not isinstance(value, str):
                return False, f"{field.field_name} must be text"

            if field.min_length and len(value) < field.min_length:
                return False, f"{field.field_name} must be at least {field.min_length} characters"

            if field.max_length and len(value) > field.max_length:
                return False, f"{field.field_name} must be at most {field.max_length} characters"

            if field.validation_regex:
                if not re.match(field.validation_regex, value):
                    return False, f"{field.field_name} format is invalid"

        elif field_type == "NUMBER":
            try:
                num_value = float(value)
            except (ValueError, TypeError):
                return False, f"{field.field_name} must be a number"

        elif field_type == "DROPDOWN":
            valid_values = [opt.get("value") for opt in (field.options or [])]
            if value not in valid_values:
                return False, f"{field.field_name} must be one of: {', '.join(valid_values)}"

        elif field_type == "MULTISELECT":
            if not isinstance(value, list):
                return False, f"{field.field_name} must be a list"
            valid_values = [opt.get("value") for opt in (field.options or [])]
            for v in value:
                if v not in valid_values:
                    return False, f"Invalid option '{v}' for {field.field_name}"

        elif field_type == "DATE":
            if isinstance(value, str):
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    return False, f"{field.field_name} must be a valid date (YYYY-MM-DD)"

        elif field_type == "DATETIME":
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    return False, f"{field.field_name} must be a valid datetime"

        elif field_type == "CHECKBOX":
            if not isinstance(value, bool):
                return False, f"{field.field_name} must be true or false"

        elif field_type == "URL":
            if not isinstance(value, str):
                return False, f"{field.field_name} must be a URL string"
            # Basic URL validation
            if not re.match(r'^https?://', value):
                return False, f"{field.field_name} must be a valid URL starting with http:// or https://"

        elif field_type == "EMAIL":
            if not isinstance(value, str):
                return False, f"{field.field_name} must be an email string"
            # Basic email validation
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', value):
                return False, f"{field.field_name} must be a valid email address"

        return True, None

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def get_default_values(
        self,
        ticket_type: Optional[str] = None,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get default values for all custom fields.

        Args:
            ticket_type: Filter by applicable ticket type.
            company: Filter by company.

        Returns:
            Dict of field_key -> default_value.
        """
        fields = self.list(active_only=True, ticket_type=ticket_type, company=company)
        defaults = {}

        for field in fields:
            if field.default_value is not None:
                # Parse default based on type
                if field.field_type.upper() == "CHECKBOX":
                    defaults[field.field_key] = field.default_value.lower() == "true"
                elif field.field_type.upper() == "NUMBER":
                    try:
                        defaults[field.field_key] = float(field.default_value)
                    except ValueError:
                        defaults[field.field_key] = None
                elif field.field_type.upper() == "MULTISELECT":
                    defaults[field.field_key] = field.default_value.split(",") if field.default_value else []
                else:
                    defaults[field.field_key] = field.default_value

        return defaults

    def build_field_schema(
        self,
        ticket_type: Optional[str] = None,
        for_portal: bool = False,
        company: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build a schema description of custom fields for form rendering.

        Args:
            ticket_type: Filter by applicable ticket type.
            for_portal: If True, only include portal-visible fields.
            company: Filter by company.

        Returns:
            List of field schema dicts.
        """
        fields = self.get_form_fields(ticket_type, for_portal, company)
        schema = []

        for field in fields:
            field_schema = {
                "key": field.field_key,
                "name": field.field_name,
                "type": field.field_type.lower(),
                "required": field.is_required,
                "default": field.default_value,
            }

            if field.options:
                field_schema["options"] = field.options

            if field.min_length:
                field_schema["minLength"] = field.min_length

            if field.max_length:
                field_schema["maxLength"] = field.max_length

            if field.validation_regex:
                field_schema["pattern"] = field.validation_regex

            schema.append(field_schema)

        return schema
