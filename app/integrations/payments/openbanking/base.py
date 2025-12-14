"""
Abstract base class for open banking providers.

All open banking implementations must inherit from BaseOpenBankingProvider
and implement all abstract methods.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from app.integrations.payments.enums import (
    OpenBankingProvider,
    ConnectionStatus,
)


# =============================================================================
# Data Transfer Objects
# =============================================================================

@dataclass
class LinkedAccount:
    """A linked bank account."""
    account_id: str  # Provider account ID
    account_number: str
    bank_code: str
    bank_name: str
    account_name: str
    account_type: str  # savings, current, domiciliary
    currency: str
    balance: Optional[Decimal] = None
    balance_date: Optional[datetime] = None
    bvn: Optional[str] = None
    connection_status: ConnectionStatus = ConnectionStatus.CONNECTED


@dataclass
class AccountTransaction:
    """A bank account transaction."""
    transaction_id: str
    date: datetime
    narration: str
    type: str  # credit, debit
    amount: Decimal
    balance: Optional[Decimal] = None
    category: Optional[str] = None
    reference: Optional[str] = None
    counterparty: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountStatement:
    """Account statement with transactions."""
    account_id: str
    account_number: str
    start_date: date
    end_date: date
    opening_balance: Decimal
    closing_balance: Decimal
    transactions: List[AccountTransaction] = field(default_factory=list)


@dataclass
class IdentityInfo:
    """Customer identity information from bank."""
    bvn: Optional[str] = None
    full_name: str = ""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Abstract Base Class
# =============================================================================

class BaseOpenBankingProvider(abc.ABC):
    """Abstract base class for open banking providers."""

    provider: OpenBankingProvider

    @abc.abstractmethod
    async def get_widget_token(
        self,
        customer_id: str,
        redirect_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get token/config for launching account linking widget.

        Args:
            customer_id: Internal customer identifier
            redirect_url: URL to redirect after linking
            metadata: Optional metadata

        Returns:
            Widget configuration (public key, token, etc.)
        """
        pass

    @abc.abstractmethod
    async def exchange_code(self, code: str) -> str:
        """
        Exchange authorization code for account ID.

        Args:
            code: Authorization code from widget callback

        Returns:
            Provider's account ID

        Raises:
            AccountLinkingError: If exchange fails
        """
        pass

    @abc.abstractmethod
    async def get_account_details(self, account_id: str) -> LinkedAccount:
        """
        Get linked account details.

        Args:
            account_id: Provider's account ID

        Returns:
            Account details

        Raises:
            AccountNotFoundError: If account not found
        """
        pass

    @abc.abstractmethod
    async def get_account_balance(self, account_id: str) -> Decimal:
        """
        Get current account balance.

        Args:
            account_id: Provider's account ID

        Returns:
            Current balance

        Raises:
            AccountSyncError: If sync fails
        """
        pass

    @abc.abstractmethod
    async def get_transactions(
        self,
        account_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[AccountTransaction]:
        """
        Get account transactions.

        Args:
            account_id: Provider's account ID
            start_date: Start date filter
            end_date: End date filter
            limit: Max transactions to return

        Returns:
            List of transactions

        Raises:
            AccountSyncError: If fetch fails
        """
        pass

    @abc.abstractmethod
    async def get_statement(
        self,
        account_id: str,
        start_date: date,
        end_date: date,
    ) -> AccountStatement:
        """
        Get account statement for a period.

        Args:
            account_id: Provider's account ID
            start_date: Statement start date
            end_date: Statement end date

        Returns:
            Statement with transactions

        Raises:
            AccountSyncError: If fetch fails
        """
        pass

    @abc.abstractmethod
    async def get_identity(self, account_id: str) -> IdentityInfo:
        """
        Get customer identity from linked account.

        Args:
            account_id: Provider's account ID

        Returns:
            Identity information

        Raises:
            AccountSyncError: If fetch fails
        """
        pass

    @abc.abstractmethod
    async def reauthorize(self, account_id: str) -> str:
        """
        Get reauthorization URL for expired connection.

        Args:
            account_id: Provider's account ID

        Returns:
            Reauthorization URL

        Raises:
            ReauthorizationRequiredError: If reauth not possible
        """
        pass

    @abc.abstractmethod
    async def unlink_account(self, account_id: str) -> bool:
        """
        Unlink a connected account.

        Args:
            account_id: Provider's account ID

        Returns:
            True if successfully unlinked
        """
        pass

    @abc.abstractmethod
    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """
        Verify webhook signature.

        Args:
            payload: Raw request body
            signature: Signature from header

        Returns:
            True if signature is valid
        """
        pass

    async def close(self) -> None:
        """Close any open connections. Override if needed."""
        pass
