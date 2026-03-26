"""Bot info views."""
from __future__ import annotations

import os

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
import httpx
from loguru import logger

from .base import error_response, json_response

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


@method_decorator(csrf_exempt, name="dispatch")
class BotInfoView(View):
    """
    GET /bot/info - Get bot information (username only, no token)
    """

    async def get(self, request: HttpRequest) -> JsonResponse:
        logger.info(f"BotInfoView GET request: method={request.method}, path={request.path}")
        if not BOT_TOKEN:
            logger.error("BotInfoView: TELEGRAM_BOT_TOKEN is not configured")
            return error_response("TELEGRAM_BOT_TOKEN is not configured", 500)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe")
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.exception(f"BotInfoView GET error: {exc}")
            return error_response(f"Failed to get bot info: {str(exc)}", 500)

        if not data.get("ok"):
            logger.error("BotInfoView: Telegram API returned ok=False")
            return error_response("Failed to get bot info", 500)

        result = data.get("result", {})
        output = {
            "username": result.get("username", ""),
            "first_name": result.get("first_name", ""),
            "bot_login_url": f"https://t.me/{result.get('username', '')}",
        }
        logger.info(f"BotInfoView GET response: {output}")
        return json_response(output)
