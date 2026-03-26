"""Base utilities for wallet views."""
from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from decimal import Decimal, InvalidOperation
from functools import wraps
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar

from asgiref.sync import sync_to_async
from django.http import HttpRequest, JsonResponse
from loguru import logger

from ..models import TelegramIdentity, WalletAccount
from ..services.authentication import AuthenticationService

if TYPE_CHECKING:
    pass

T = TypeVar("T")
P = ParamSpec("P")
AuthenticatedViewMethod = Callable[
    Concatenate[object, HttpRequest, "TelegramIdentity", P],
    Awaitable[JsonResponse],
]


def parse_json(request: HttpRequest) -> dict[str, Any]:
    """Parse JSON body from request."""
    import json
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Invalid JSON")


def authenticate_request(request: HttpRequest) -> str | None:
    """Extract and validate token from request."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning(
            f"authenticate_request: missing/invalid Authorization header path={request.path}"
        )
        return None
    return auth_header[7:]


async def run_sync(function: Callable[[], T]) -> T:
    """Run a synchronous function in a thread-safe async context."""
    return await sync_to_async(function, thread_sensitive=True)()


async def get_identity(request: HttpRequest) -> TelegramIdentity | None:
    """Resolve TelegramIdentity from request token."""
    token = authenticate_request(request)
    if token is None:
        return None
    identity = await AuthenticationService.resolve_identity(token)
    if identity is None:
        logger.warning(
            f"get_identity: token not resolved path={request.path} token_prefix={token[:8]}"
        )
    return identity


async def get_account_for_identity(identity: TelegramIdentity) -> WalletAccount | None:
    """Load wallet account for identity, returning None when absent."""
    try:
        return await run_sync(lambda: identity.account)
    except WalletAccount.DoesNotExist:
        return None


def require_auth(
    view_method: AuthenticatedViewMethod[P],
) -> Callable[Concatenate[object, HttpRequest, P], Awaitable[JsonResponse]]:
    """Decorator that requires bearer-authenticated Telegram identity."""

    @wraps(view_method)
    async def wrapper(
        self: object,
        request: HttpRequest,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> JsonResponse:
        identity = await get_identity(request)
        if identity is None:
            logger.warning(f"require_auth: unauthorized path={request.path}")
            return error_response("Authentication required", status=401)
        logger.info(
            f"require_auth: authorized path={request.path} "
            f"telegram_user_id={identity.telegram_user_id}"
        )
        return await view_method(self, request, identity, *args, **kwargs)

    return wrapper


def json_response(data: dict[str, Any], status: int = 200) -> JsonResponse:
    """Create a consistent JSON success response."""
    return JsonResponse({"status": "ok", "data": data}, status=status)


def error_response(message: str, status: int = 400) -> JsonResponse:
    """Create a consistent JSON error response."""
    return JsonResponse({"status": "error", "message": message}, status=status)


def parse_decimal(value: str | float | None, field_name: str) -> Decimal:
    """Parse a value to Decimal with validation."""
    if value is None:
        raise ValueError(f"{field_name} is required")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid {field_name}")


def validate_positive_decimal(value: str | float | None, field_name: str) -> Decimal:
    """Parse and validate a positive decimal value."""
    decimal_value = parse_decimal(value, field_name)
    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return decimal_value


def generate_deterministic_address(telegram_user_id: int) -> str:
    """Generate a deterministic address from telegram user ID."""
    hash_input = f"address:{telegram_user_id}".encode()
    return "0x" + hashlib.md5(hash_input).hexdigest()[:40]
