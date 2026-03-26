"""Async authentication service for Telegram-based authentication and token management."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.db import transaction
from loguru import logger

from ..constants import DEFAULT_STARTING_CASH
from ..models import AgentPreference, TelegramIdentity, WalletAccount

if TYPE_CHECKING:
    from .auth_sessions import AuthSession


@dataclass(frozen=True)
class AuthResult:
    """Result of a successful authentication."""

    token: str
    telegram_user_id: int
    username: str


class AuthenticationService:
    """Service for Telegram-based authentication and token management."""

    @staticmethod
    def _generate_token() -> str:
        """Generate a secure random token."""
        return secrets.token_hex(32)

    @classmethod
    async def authenticate_telegram(
        cls,
        telegram_user_id: int,
        username: str = "",
    ) -> AuthResult:
        """
        Authenticate a Telegram user, creating or updating their identity.

        This is idempotent - calling with the same telegram_user_id will
        return the same token.
        """
        def _do_auth() -> TelegramIdentity:
            with transaction.atomic():
                identity, created = TelegramIdentity.objects.select_for_update().get_or_create(
                    telegram_user_id=telegram_user_id,
                    defaults={"username": username, "token": cls._generate_token()},
                )

                if not created:
                    if username and identity.username != username:
                        identity.username = username
                        identity.save(update_fields=["username"])

                wallet_account, _ = WalletAccount.objects.select_for_update().get_or_create(
                    identity=identity,
                    defaults={"cash_balance": DEFAULT_STARTING_CASH, "initial_cash": DEFAULT_STARTING_CASH},
                )

                AgentPreference.objects.select_for_update().get_or_create(
                    account=wallet_account,
                    defaults={
                        "selected_agents": AgentPreference.default_selected_advisors(),
                        "allocation": AgentPreference.default_advisor_weights(),
                        "selected_advisors": AgentPreference.default_selected_advisors(),
                        "advisor_weights": AgentPreference.default_advisor_weights(),
                        "risk_profile": AgentPreference.default_risk_profile(),
                    },
                )
                return identity

        identity = await sync_to_async(_do_auth)()

        return AuthResult(
            token=identity.token,
            telegram_user_id=identity.telegram_user_id,
            username=identity.username,
        )

    @staticmethod
    async def validate_token(token: str) -> TelegramIdentity | None:
        """
        Validate a token and return the associated TelegramIdentity.

        Returns None if the token is invalid or not found.
        """
        try:
            return await TelegramIdentity.objects.select_related("account").aget(token=token)
        except TelegramIdentity.DoesNotExist:
            return None

    @classmethod
    async def resolve_identity(cls, token: str) -> TelegramIdentity | None:
        """
        Resolve a token into a TelegramIdentity.

        Supports both:
        - long-lived identity tokens (`/auth/telegram`)
        - session tokens (`/auth/complete`, `/auth/telegram/widget`)
        """
        from .auth_sessions import AuthSession

        identity = await cls.validate_token(token)
        if identity is not None:
            return identity

        session = await AuthSession.validate_session(token)
        if session is None:
            return None

        try:
            return await TelegramIdentity.objects.select_related("account").aget(
                telegram_user_id=session.telegram_user_id
            )
        except TelegramIdentity.DoesNotExist:
            logger.warning(
                "resolve_identity: session token maps to missing TelegramIdentity "
                f"(telegram_user_id={session.telegram_user_id})"
            )
            return None

    @staticmethod
    async def get_account(token: str) -> WalletAccount | None:
        """Get the wallet account associated with a token."""
        identity = await AuthenticationService.resolve_identity(token)
        if identity is None:
            return None
        try:
            return await WalletAccount.objects.aget(identity=identity)
        except WalletAccount.DoesNotExist:
            return None
