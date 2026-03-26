"""Authentication views including Telegram Login Widget."""
from __future__ import annotations

import os
import secrets
from typing import Any

from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from loguru import logger

from ..constants import DEFAULT_STARTING_CASH
from ..models import AgentPreference, TelegramIdentity, WalletAccount
from ..services.auth_sessions import AuthSession, PendingAuth
from ..services.authentication import AuthenticationService
from ..services.telegram_auth import TelegramAuthService
from .base import error_response, json_response, parse_json, run_sync


def _telegram_bot_tokens() -> list[str]:
    tokens: list[str] = []
    for env_name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_STAGE_BOT_TOKEN"):
        token = os.getenv(env_name, "").strip()
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def _ensure_identity_account_and_preferences(telegram_user_id: int) -> None:
    """Provision identity, wallet account, and default preferences for a user."""
    identity, _ = TelegramIdentity.objects.get_or_create(
        telegram_user_id=telegram_user_id,
        defaults={"username": "", "token": secrets.token_hex(32)},
    )
    WalletAccount.objects.get_or_create(
        identity=identity,
        defaults={"cash_balance": DEFAULT_STARTING_CASH, "initial_cash": DEFAULT_STARTING_CASH},
    )
    AgentPreference.objects.get_or_create(
        account=identity.account,
        defaults={
            "selected_agents": AgentPreference.default_selected_advisors(),
            "allocation": AgentPreference.default_advisor_weights(),
            "selected_advisors": AgentPreference.default_selected_advisors(),
            "advisor_weights": AgentPreference.default_advisor_weights(),
            "risk_profile": AgentPreference.default_risk_profile(),
        },
    )


@method_decorator(csrf_exempt, name="dispatch")
class TelegramAuthView(View):
    async def post(self, request: HttpRequest) -> JsonResponse:
        logger.info(f"TelegramAuthView POST body={request.body.decode(errors='replace')}")
        try:
            data = parse_json(request)
            logger.info(f"TelegramAuthView input: {data}")
        except ValueError:
            return error_response("Invalid JSON", 400)

        telegram_user_id = data.get("telegram_user_id")
        username = data.get("username", "")
        logger.info(f"TelegramAuthView: user_id={telegram_user_id}, username={username}")

        if not telegram_user_id or not isinstance(telegram_user_id, int):
            return error_response("telegram_user_id is required", 400)

        try:
            result = await AuthenticationService.authenticate_telegram(telegram_user_id, username)
            logger.info(
                f"TelegramAuthView result: token={result.token[:20]}..., user_id={result.telegram_user_id}"
            )
        except DatabaseError as exc:
            logger.exception(f"TelegramAuthView error: {exc}")
            return error_response(str(exc), 500)

        return json_response(
            {
                "token": result.token,
                "telegram_user_id": result.telegram_user_id,
                "username": result.username,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class PendingAuthView(View):
    async def post(self, request: HttpRequest) -> JsonResponse:
        logger.info(f"PendingAuthView POST body={request.body.decode(errors='replace')}")
        try:
            data = parse_json(request)
            logger.info(f"PendingAuthView input: {data}")
        except ValueError:
            data = {}
        token = data.get("token")

        pending = await PendingAuth.create_pending_auth(token=token)
        logger.info(f"PendingAuthView created: token={pending.token}, completed={pending.completed}")
        output = {
            "token": pending.token,
            "expires_at": pending.expires_at.isoformat(),
        }
        logger.info(f"PendingAuthView POST response: {output}")
        return json_response(output)

    async def get(self, request: HttpRequest, token: str) -> JsonResponse:
        logger.info(f"PendingAuthView GET token={token}")

        pending = await PendingAuth.get_pending(token)

        if pending is not None:
            logger.info(f"PendingAuthView: token={token} is PENDING")
            output = {
                "token": token,
                "status": "pending",
                "telegram_user_id": None,
            }
            logger.info(f"PendingAuthView GET response: {output}")
            return json_response(output)

        try:
            completed = await PendingAuth.objects.aget(token=token, completed=True)
            logger.info(
                "PendingAuthView: token={} is COMPLETED session={}...",
                token,
                completed.session_token[:20] if completed.session_token else None,
            )
            output = {
                "token": token,
                "status": "completed",
                "telegram_user_id": completed.telegram_user_id,
                "session_token": completed.session_token,
            }
            logger.info(f"PendingAuthView GET response: {output}")
            return json_response(output)
        except PendingAuth.DoesNotExist:
            logger.warning(f"PendingAuthView: token={token} NOT FOUND")
            return error_response("Token not found", 404)


@method_decorator(csrf_exempt, name="dispatch")
class CompleteAuthView(View):
    async def post(self, request: HttpRequest) -> JsonResponse:
        logger.info(f"CompleteAuthView POST body={request.body.decode(errors='replace')}")
        try:
            data = parse_json(request)
            logger.info(f"CompleteAuthView input: {data}")
        except ValueError:
            return error_response("Invalid JSON", 400)

        token = data.get("token")
        telegram_user_id = data.get("telegram_user_id")

        logger.info(f"CompleteAuthView: token={token}, user_id={telegram_user_id}")

        if not token or not telegram_user_id:
            return error_response("token and telegram_user_id required", 400)

        try:
            session = await AuthSession.create_session(telegram_user_id)
            logger.info(f"CompleteAuthView: session={session.session_token[:20]}...")
            pending = await PendingAuth.complete_auth(token, telegram_user_id, session.session_token)
            if pending is None:
                logger.error(f"CompleteAuthView: FAILED to complete token={token}")
                return error_response("Invalid token", 400)
            await run_sync(lambda: _ensure_identity_account_and_preferences(telegram_user_id))
        except DatabaseError as exc:
            logger.exception(f"CompleteAuthView database error: {exc}")
            return error_response(str(exc), 500)

        logger.info(f"CompleteAuthView: SUCCESS token={token}")
        output = {
            "status": "completed",
            "session_token": session.session_token,
            "user_id": telegram_user_id,
        }
        logger.info(f"CompleteAuthView POST response: {output}")
        return json_response(output)


@method_decorator(csrf_exempt, name="dispatch")
class SessionValidateView(View):
    async def get(self, request: HttpRequest, token: str) -> JsonResponse:
        logger.info(f"SessionValidate GET token={token}")
        session = await AuthSession.validate_session(token)

        if session is None:
            logger.warning(f"SessionValidate: INVALID token={token}")
            return error_response("Invalid session", 401)

        logger.info(f"SessionValidate: VALID token={token[:20]}...")
        output = {
            "valid": True,
            "user_id": session.telegram_user_id,
            "expires_at": session.expires_at,
        }
        logger.info(f"SessionValidate GET response: {output}")
        return json_response(output)


@method_decorator(csrf_exempt, name="dispatch")
class HealthView(View):
    async def get(self, request: HttpRequest) -> JsonResponse:
        return JsonResponse({"status": "ok"})


@method_decorator(csrf_exempt, name="dispatch")
class WebSocketView(View):
    async def get(self, request: HttpRequest) -> JsonResponse:
        return json_response({"test_mode": True})


@method_decorator(csrf_exempt, name="dispatch")
class TelegramLoginWidgetView(View):
    async def post(self, request: HttpRequest) -> JsonResponse:
        logger.info(f"TelegramLoginWidget POST body={request.body.decode(errors='replace')}")
        try:
            data = parse_json(request)
            logger.info(f"TelegramLoginWidget input: {data}")
        except ValueError:
            return error_response("Invalid JSON", 400)

        user = None
        for bot_token in _telegram_bot_tokens():
            user = TelegramAuthService(bot_token).verify_login_widget_data(data)
            if user is not None:
                break
        if user is None:
            logger.warning("TelegramLoginWidget: Invalid Telegram login")
            return error_response("Invalid Telegram login", 401)

        # Provision identity/account/preferences for widget-based logins too.
        await AuthenticationService.authenticate_telegram(user.user_id, user.username or "")

        session = await AuthSession.create_session(user.user_id)
        logger.info(f"TelegramLoginWidget session={session.session_token[:20]}...")

        output = {
            "session_token": session.session_token,
            "user_id": user.user_id,
            "username": user.username,
        }
        logger.info(f"TelegramLoginWidget POST response: {output}")
        return json_response(output)
