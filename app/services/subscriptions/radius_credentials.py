"""RADIUS credential generation service.

Generates usernames and passwords for RADIUS authentication.
Supports multiple username formats and configurable password complexity.
"""
from __future__ import annotations

import re
import secrets
import string
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .radius_credentials_types import (
    RADIUSCredentialConfig,
    PasswordComplexityConfig,
    UsernameTemplateConfig,
    SequentialConfig,
    GeneratedCredentials,
    CredentialGenerationContext,
    UsernameFormatType,
)
from .radius_credentials_config import RADIUSCredentialConfigService
from app.services.errors import ValidationError, NotFoundError

if TYPE_CHECKING:
    from app.auth import Principal
    from app.models.subscription import Subscription
    from app.models.party import Party

__all__ = [
    "RADIUSCredentialService",
    "CredentialGenerationContext",
    "GeneratedCredentials",
]


class RADIUSCredentialService:
    """Service for generating RADIUS credentials.

    Supports:
    - Template-based usernames ({email}, {first_name}.{last_name}, etc.)
    - Sequential usernames (USER0001, USER0002)
    - Email-based usernames
    - Phone-based usernames
    - Subscription ID-based usernames

    Password generation uses cryptographically secure random generation
    with configurable complexity (length, character types, etc.).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal
        self._config_service = RADIUSCredentialConfigService(db, principal)

    def get_config(self) -> RADIUSCredentialConfig:
        """Get current configuration."""
        return self._config_service.get_config()

    # =========================================================================
    # Main Generation Methods
    # =========================================================================

    def generate_credentials(
        self,
        context: CredentialGenerationContext,
        generate_username: bool = True,
        generate_password: bool = True,
    ) -> GeneratedCredentials:
        """Generate RADIUS credentials for a subscription.

        Args:
            context: Generation context with party/subscription info.
            generate_username: Whether to generate username.
            generate_password: Whether to generate password.

        Returns:
            GeneratedCredentials with username and password.
        """
        config = self.get_config()

        username = ""
        password = ""

        if generate_username:
            username = self.generate_unique_username(context, config)

        if generate_password:
            password = self._generate_password(config.password)

        return GeneratedCredentials(
            username=username,
            password=password,
            generated_at=datetime.now(timezone.utc),
            format_used=config.username.format_type,
        )

    def generate_unique_username(
        self,
        context: CredentialGenerationContext,
        config: Optional[RADIUSCredentialConfig] = None,
        max_attempts: int = 100,
    ) -> str:
        """Generate a unique username with collision handling.

        Args:
            context: Generation context.
            config: Optional config override.
            max_attempts: Maximum attempts to find unique username.

        Returns:
            Unique username.

        Raises:
            ValidationError: If unable to generate unique username.
        """
        config = config or self.get_config()
        format_type = UsernameFormatType(config.username.format_type)

        for attempt in range(max_attempts):
            if format_type == UsernameFormatType.SEQUENTIAL:
                # Sequential always generates unique
                username = self._generate_sequential_username(config.sequential)
            else:
                username = self._generate_username(context, config)

                # Add suffix on collision
                if attempt > 0:
                    username = f"{username}{attempt}"

            # Apply transformations
            username = self._apply_transformations(username, config.username)

            # Check uniqueness
            if self.validate_username_unique(username):
                return username

        raise ValidationError(
            f"Unable to generate unique username after {max_attempts} attempts"
        )

    def regenerate_credentials(
        self,
        subscription_id: int,
        regenerate_username: bool = True,
        regenerate_password: bool = True,
    ) -> GeneratedCredentials:
        """Regenerate credentials for an existing subscription.

        Args:
            subscription_id: Subscription to regenerate for.
            regenerate_username: Whether to regenerate username.
            regenerate_password: Whether to regenerate password.

        Returns:
            New credentials.

        Raises:
            NotFoundError: If subscription not found.
        """
        from app.models.subscription import Subscription
        from app.models.party import Party

        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()

        if not subscription:
            raise NotFoundError(f"Subscription {subscription_id} not found")

        party = self.db.query(Party).filter(
            Party.id == subscription.party_id
        ).first()

        # Build context
        context = self._build_context_from_subscription(subscription, party)

        # Generate new credentials
        credentials = self.generate_credentials(
            context,
            generate_username=regenerate_username,
            generate_password=regenerate_password,
        )

        # Update subscription
        if regenerate_username:
            subscription.ppp_username = credentials.username
        if regenerate_password:
            subscription.ppp_password = credentials.password

        self.db.flush()

        return credentials

    def regenerate_bulk(
        self,
        subscription_ids: List[int],
        regenerate_username: bool = True,
        regenerate_password: bool = True,
    ) -> Dict[str, Any]:
        """Bulk regenerate credentials.

        Args:
            subscription_ids: List of subscription IDs.
            regenerate_username: Whether to regenerate usernames.
            regenerate_password: Whether to regenerate passwords.

        Returns:
            Summary of results.
        """
        results = {
            "success": [],
            "failed": [],
            "total": len(subscription_ids),
        }

        for sub_id in subscription_ids:
            try:
                creds = self.regenerate_credentials(
                    sub_id,
                    regenerate_username=regenerate_username,
                    regenerate_password=regenerate_password,
                )
                results["success"].append({
                    "subscription_id": sub_id,
                    "username": creds.username if regenerate_username else None,
                })
            except Exception as e:
                results["failed"].append({
                    "subscription_id": sub_id,
                    "error": str(e),
                })

        return results

    def preview_generation(
        self,
        context: CredentialGenerationContext,
    ) -> Dict[str, Any]:
        """Preview what credentials would be generated.

        Useful for UI preview without actually generating.

        Args:
            context: Generation context.

        Returns:
            Preview data.
        """
        config = self.get_config()

        username = self._generate_username(context, config)
        username = self._apply_transformations(username, config.username)

        # Get password char pool info
        password_info = {
            "length_range": f"{config.password.min_length}-{config.password.max_length}",
            "includes": [],
        }
        if config.password.include_lowercase:
            password_info["includes"].append("lowercase")
        if config.password.include_uppercase:
            password_info["includes"].append("uppercase")
        if config.password.include_digits:
            password_info["includes"].append("digits")
        if config.password.include_special:
            password_info["includes"].append(f"special ({config.password.special_chars})")

        return {
            "username_preview": username,
            "format_type": config.username.format_type,
            "password_complexity": password_info,
            "is_unique": self.validate_username_unique(username),
        }

    # =========================================================================
    # Username Generation Methods
    # =========================================================================

    def _generate_username(
        self,
        context: CredentialGenerationContext,
        config: RADIUSCredentialConfig,
    ) -> str:
        """Generate username based on format type.

        Args:
            context: Generation context.
            config: Configuration.

        Returns:
            Generated username (before transformations).
        """
        format_type = UsernameFormatType(config.username.format_type)

        if format_type == UsernameFormatType.TEMPLATE:
            return self._format_template_username(context, config)
        elif format_type == UsernameFormatType.SEQUENTIAL:
            return self._generate_sequential_username(config.sequential)
        elif format_type == UsernameFormatType.EMAIL:
            if context.email:
                return context.email
            # Fall back to sequential if no email available
            return self._generate_sequential_username(config.sequential)
        elif format_type == UsernameFormatType.PHONE:
            phone = context.phone or ""
            # Strip non-digits
            digits = re.sub(r"[^\d]", "", phone)
            if digits:
                return digits
            # Fall back to sequential if no phone available
            return self._generate_sequential_username(config.sequential)
        elif format_type == UsernameFormatType.SUBSCRIPTION_ID:
            if context.subscription_id and context.subscription_id > 0:
                return f"SUB-{context.subscription_id}"
            # Fall back to sequential for new subscriptions (id=0)
            return self._generate_sequential_username(config.sequential)
        else:
            return self._generate_sequential_username(config.sequential)

    def _format_template_username(
        self,
        context: CredentialGenerationContext,
        config: RADIUSCredentialConfig,
    ) -> str:
        """Format username using template with placeholders.

        Supported placeholders:
        - {email} - Party primary email
        - {phone} - Party primary phone (digits only)
        - {party_id} - Party ID
        - {subscription_id} - Subscription ID
        - {first_name} - Party first name
        - {last_name} - Party last name
        - {plan_code} - Subscription plan code
        - {tariff_name} - Tariff title
        - {domain} - Configured domain
        """
        template = config.username.template

        # Build replacement map
        replacements = {
            "email": context.email or "",
            "phone": re.sub(r"[^\d]", "", context.phone or ""),
            "party_id": str(context.party_id),
            "subscription_id": str(context.subscription_id),
            "first_name": context.first_name or "",
            "last_name": context.last_name or "",
            "plan_code": context.plan_code or "",
            "tariff_name": context.tariff_name or "",
            "domain": config.username.domain or "",
        }

        # Replace placeholders
        result = template
        for key, value in replacements.items():
            result = result.replace(f"{{{key}}}", value)

        return result

    def _generate_sequential_username(
        self,
        sequential_config: SequentialConfig,
    ) -> str:
        """Generate sequential username (USER0001, USER0002, etc.).

        Uses database-backed counter with row-level locking.

        Args:
            sequential_config: Sequential configuration.

        Returns:
            Next sequential username.
        """
        from app.models.radius_credential_sequence import RADIUSCredentialSequence

        # Ensure sequence exists using INSERT ... ON CONFLICT to avoid race conditions
        stmt = insert(RADIUSCredentialSequence).values(
            sequence_name="default",
            current_value=sequential_config.start_from - 1,
            prefix=sequential_config.prefix,
            padding_length=sequential_config.padding_length,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["sequence_name"])
        self.db.execute(stmt)
        self.db.flush()

        # Now get the sequence with FOR UPDATE lock
        sequence = (
            self.db.query(RADIUSCredentialSequence)
            .filter(RADIUSCredentialSequence.sequence_name == "default")
            .with_for_update()
            .first()
        )

        # Increment and get username
        username = sequence.increment_and_get()
        self.db.flush()

        return username

    def _apply_transformations(
        self,
        username: str,
        config: UsernameTemplateConfig,
    ) -> str:
        """Apply transformations to username.

        Args:
            username: Raw username.
            config: Username configuration.

        Returns:
            Transformed username.
        """
        result = username

        # Strip special characters if configured
        if config.strip_special:
            # Keep alphanumeric, dots, underscores, hyphens, and @
            result = re.sub(r"[^\w.@-]", "", result)

        # Convert to lowercase if configured
        if config.lowercase:
            result = result.lower()

        # Truncate to max length
        if len(result) > config.max_length:
            result = result[:config.max_length]

        return result

    # =========================================================================
    # Password Generation Methods
    # =========================================================================

    def _generate_password(
        self,
        config: PasswordComplexityConfig,
    ) -> str:
        """Generate secure random password.

        Uses secrets module for cryptographically secure randomness.

        Args:
            config: Password complexity configuration.

        Returns:
            Generated password.
        """
        # Build character pool
        pool = self._config_service.get_password_char_pool()
        using_fallback = False

        if not pool:
            # Fallback if no character types selected - use sensible defaults
            pool = string.ascii_letters + string.digits
            using_fallback = True

        # Determine length
        length = secrets.randbelow(config.max_length - config.min_length + 1) + config.min_length

        # Generate password
        password = "".join(secrets.choice(pool) for _ in range(length))

        # Ensure at least one character from each enabled category
        # Skip complexity enforcement if using fallback (no char types configured)
        if not using_fallback:
            password = self._ensure_complexity(password, config)

        return password

    def _ensure_complexity(
        self,
        password: str,
        config: PasswordComplexityConfig,
    ) -> str:
        """Ensure password meets complexity requirements.

        Replaces random positions with required character types.

        Args:
            password: Initial password.
            config: Complexity configuration.

        Returns:
            Password meeting all requirements.
        """
        password_list = list(password)
        position = 0

        lowercase = "abcdefghijklmnopqrstuvwxyz"
        uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        digits = "0123456789"

        if config.exclude_ambiguous:
            lowercase = lowercase.replace("l", "")
            uppercase = uppercase.replace("I", "").replace("O", "")
            digits = digits.replace("0", "").replace("1", "")

        # Ensure each required character type is present
        if config.include_lowercase and not any(c in lowercase for c in password):
            if position < len(password_list):
                password_list[position] = secrets.choice(lowercase)
                position += 1

        if config.include_uppercase and not any(c in uppercase for c in password):
            if position < len(password_list):
                password_list[position] = secrets.choice(uppercase)
                position += 1

        if config.include_digits and not any(c in digits for c in password):
            if position < len(password_list):
                password_list[position] = secrets.choice(digits)
                position += 1

        if config.include_special and not any(c in config.special_chars for c in password):
            if position < len(password_list):
                password_list[position] = secrets.choice(config.special_chars)
                position += 1

        # Shuffle to avoid predictable positions
        password_chars = password_list[:]
        secrets.SystemRandom().shuffle(password_chars)

        return "".join(password_chars)

    # =========================================================================
    # Validation Methods
    # =========================================================================

    def validate_username_unique(
        self,
        username: str,
        exclude_subscription_id: Optional[int] = None,
    ) -> bool:
        """Check if username is unique.

        Args:
            username: Username to check.
            exclude_subscription_id: Subscription to exclude (for updates).

        Returns:
            True if username is unique.
        """
        from app.models.subscription import Subscription

        query = self.db.query(Subscription).filter(
            Subscription.ppp_username == username
        )

        if exclude_subscription_id:
            query = query.filter(Subscription.id != exclude_subscription_id)

        return query.first() is None

    # =========================================================================
    # Sequence Management
    # =========================================================================

    def get_current_sequence(self) -> Dict[str, Any]:
        """Get current sequence state.

        Returns:
            Sequence information.
        """
        from app.models.radius_credential_sequence import RADIUSCredentialSequence

        sequence = (
            self.db.query(RADIUSCredentialSequence)
            .filter(RADIUSCredentialSequence.sequence_name == "default")
            .first()
        )

        if not sequence:
            config = self.get_config()
            return {
                "current_value": 0,
                "next_username": f"{config.sequential.prefix}0001",
                "prefix": config.sequential.prefix,
                "padding_length": config.sequential.padding_length,
            }

        return {
            "current_value": sequence.current_value,
            "next_username": sequence.get_next_username(),
            "prefix": sequence.prefix,
            "padding_length": sequence.padding_length,
        }

    def reset_sequence(
        self,
        new_value: int = 0,
        new_prefix: Optional[str] = None,
        new_padding_length: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Reset the sequential counter.

        Args:
            new_value: New counter value (default 0).
            new_prefix: Optional new prefix.
            new_padding_length: Optional new padding length.

        Returns:
            Updated sequence info.
        """
        from app.models.radius_credential_sequence import RADIUSCredentialSequence

        sequence = (
            self.db.query(RADIUSCredentialSequence)
            .filter(RADIUSCredentialSequence.sequence_name == "default")
            .with_for_update()
            .first()
        )

        if not sequence:
            config = self.get_config()
            sequence = RADIUSCredentialSequence(
                sequence_name="default",
                current_value=new_value,
                prefix=new_prefix or config.sequential.prefix,
                padding_length=new_padding_length or config.sequential.padding_length,
            )
            self.db.add(sequence)
        else:
            sequence.current_value = new_value
            if new_prefix:
                sequence.prefix = new_prefix
            if new_padding_length:
                sequence.padding_length = new_padding_length

        self.db.flush()

        return self.get_current_sequence()

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_context_from_subscription(
        self,
        subscription: "Subscription",
        party: Optional["Party"],
    ) -> CredentialGenerationContext:
        """Build generation context from subscription and party.

        Args:
            subscription: Subscription model.
            party: Party model (optional).

        Returns:
            CredentialGenerationContext.
        """
        tariff_name = None
        if subscription.tariff:
            tariff_name = subscription.tariff.title

        return CredentialGenerationContext(
            subscription_id=subscription.id,
            party_id=subscription.party_id,
            first_name=party.first_name if party else None,
            last_name=party.last_name if party else None,
            email=party.primary_email if party else None,
            phone=party.primary_phone if party else None,
            plan_code=subscription.plan_name,
            tariff_name=tariff_name,
        )

    def build_context(
        self,
        subscription_id: int,
        party_id: int,
        tariff_id: Optional[int] = None,
    ) -> CredentialGenerationContext:
        """Build generation context from IDs.

        Fetches party and tariff info from database.

        Args:
            subscription_id: Subscription ID.
            party_id: Party ID.
            tariff_id: Optional tariff ID.

        Returns:
            CredentialGenerationContext.
        """
        from app.models.party import Party
        from app.models.tariff import Tariff

        party = self.db.query(Party).filter(Party.id == party_id).first()

        tariff_name = None
        if tariff_id:
            tariff = self.db.query(Tariff).filter(Tariff.id == tariff_id).first()
            if tariff:
                tariff_name = tariff.title

        return CredentialGenerationContext(
            subscription_id=subscription_id,
            party_id=party_id,
            first_name=party.first_name if party else None,
            last_name=party.last_name if party else None,
            email=party.primary_email if party else None,
            phone=party.primary_phone if party else None,
            tariff_name=tariff_name,
        )

    def get_format_types(self) -> List[Dict[str, str]]:
        """Get available username format types.

        Returns:
            List of format type options for UI.
        """
        return [
            {
                "value": UsernameFormatType.TEMPLATE.value,
                "label": "Template",
                "description": "Use template with placeholders like {email}, {first_name}",
            },
            {
                "value": UsernameFormatType.SEQUENTIAL.value,
                "label": "Sequential",
                "description": "Generate sequential usernames like USER0001, USER0002",
            },
            {
                "value": UsernameFormatType.EMAIL.value,
                "label": "Email",
                "description": "Use party's primary email as username",
            },
            {
                "value": UsernameFormatType.PHONE.value,
                "label": "Phone",
                "description": "Use party's phone number as username",
            },
            {
                "value": UsernameFormatType.SUBSCRIPTION_ID.value,
                "label": "Subscription ID",
                "description": "Use subscription ID (SUB-123)",
            },
        ]
