"""Telegram bot for wallet authentication - Pull mode (long polling)."""
from __future__ import annotations

import logging
import os
import secrets
from typing import Any

import httpx
from asgiref.sync import sync_to_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Conflict
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DJANGO_SETTINGS_MODULE = os.getenv("DJANGO_SETTINGS_MODULE", "config.settings")
MINIAPP_URL = "https://t.me/usd_printer_bot?startapp"

_DJANGO_READY = False
_BOT_JSON_EVENT_MODEL = None


def _parse_major_minor(version: str) -> tuple[int, int]:
    """Parse MAJOR.MINOR from a version string without regex/try-except."""
    parts = version.split(".")
    major_str = parts[0] if parts else "0"
    major = int(major_str) if major_str.isdigit() else 0

    minor = 0
    if len(parts) > 1:
        minor_digits = ""
        for char in parts[1]:
            if char.isdigit():
                minor_digits += char
                continue
            break
        if minor_digits:
            minor = int(minor_digits)

    return major, minor


def _dependency_compatibility_error() -> str | None:
    """Return a startup error message when runtime deps are incompatible."""
    import telegram

    ptb_version = str(getattr(telegram, "__version__", "0.0"))
    httpx_version = str(getattr(httpx, "__version__", "0.0"))
    ptb_major, _ = _parse_major_minor(ptb_version)
    httpx_major, httpx_minor = _parse_major_minor(httpx_version)

    if ptb_major < 21 and (httpx_major, httpx_minor) >= (0, 28):
        return (
            f"Incompatible dependencies: python-telegram-bot {ptb_version} with httpx {httpx_version}. "
            "Run bot with project venv (`.venv/bin/python -m bot.telegram_bot`) "
            "or install compatible versions (`python-telegram-bot>=21,<22` and `httpx<0.28`)."
        )

    return None


def _ensure_django_ready() -> bool:
    """Initialize Django lazily so bot can write JSON logs into Postgres."""
    global _DJANGO_READY
    if _DJANGO_READY:
        return True

    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS_MODULE)
        import django

        django.setup()
        _DJANGO_READY = True
        return True
    except Exception as exc:
        logger.warning("Django setup skipped in bot runtime: %s", exc)
        return False


def _get_bot_json_event_model() -> Any | None:
    """Return wallet BotJsonEvent model when Django is available."""
    global _BOT_JSON_EVENT_MODEL
    if _BOT_JSON_EVENT_MODEL is not None:
        return _BOT_JSON_EVENT_MODEL
    if not _ensure_django_ready():
        return None
    try:
        from wallet.models import BotJsonEvent

        _BOT_JSON_EVENT_MODEL = BotJsonEvent
        return _BOT_JSON_EVENT_MODEL
    except Exception as exc:
        logger.warning("BotJsonEvent model unavailable: %s", exc)
        return None


def _extract_update_ids(update: Update | None) -> tuple[int | None, int | None, int | None]:
    """Extract update/user/chat IDs from telegram update when possible."""
    if update is None:
        return None, None, None

    update_id = getattr(update, "update_id", None)
    telegram_user_id = None
    chat_id = None

    user = getattr(update, "effective_user", None)
    if user is not None:
        telegram_user_id = getattr(user, "id", None)

    chat = getattr(update, "effective_chat", None)
    if chat is not None:
        chat_id = getattr(chat, "id", None)

    return update_id, telegram_user_id, chat_id


def _safe_telegram_payload(update: Update | None) -> dict[str, Any]:
    if update is None:
        return {}
    try:
        return update.to_dict()
    except Exception:
        return {"raw_update_repr": repr(update)}


def _persist_json_event_sync(
    *,
    category: str,
    payload: Any,
    update: Update | None = None,
    telegram_user_id: int | None = None,
    chat_id: int | None = None,
) -> None:
    """Persist a raw JSON payload into BotJsonEvent table, best-effort."""
    model = _get_bot_json_event_model()
    if model is None:
        return

    update_id, update_user_id, update_chat_id = _extract_update_ids(update)
    resolved_user_id = telegram_user_id if telegram_user_id is not None else update_user_id
    resolved_chat_id = chat_id if chat_id is not None else update_chat_id

    try:
        event = model.objects.create(
            category=category,
            telegram_update_id=update_id,
            telegram_user_id=resolved_user_id,
            chat_id=resolved_chat_id,
            payload=payload,
        )
        logger.info(
            "Saved bot JSON event id=%s category=%s update_id=%s user_id=%s chat_id=%s",
            event.id,
            category,
            update_id,
            resolved_user_id,
            resolved_chat_id,
        )
    except Exception as exc:
        logger.warning("Failed to persist bot JSON event category=%s: %s", category, exc)


async def _persist_json_event_async(
    *,
    category: str,
    payload: Any,
    update: Update | None = None,
    telegram_user_id: int | None = None,
    chat_id: int | None = None,
) -> None:
    """Async wrapper for Django ORM writes from telegram async handlers."""
    await sync_to_async(_persist_json_event_sync, thread_sensitive=True)(
        category=category,
        payload=payload,
        update=update,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
    )


def notify_backend_complete(token: str, user_id: int) -> bool:
    """Notify backend that auth is complete."""
    request_payload = {"token": token, "telegram_user_id": user_id}
    _persist_json_event_sync(
        category="backend_auth_complete_request",
        payload=request_payload,
        telegram_user_id=user_id,
    )
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/auth/complete",
            json=request_payload,
            timeout=10.0,
        )
        response_payload: dict[str, Any] = {
            "status_code": resp.status_code,
            "body": resp.text,
        }
        _persist_json_event_sync(
            category="backend_auth_complete_response",
            payload=response_payload,
            telegram_user_id=user_id,
        )
        logger.info(f"Backend response: {resp.status_code} - {resp.text}")
        return resp.status_code == 200
    except Exception as e:
        _persist_json_event_sync(
            category="backend_auth_complete_error",
            payload={"error": str(e)},
            telegram_user_id=user_id,
        )
        logger.error(f"Failed to notify backend: {e}")
        return False


def create_pending_auth() -> str | None:
    """Create a pending auth on backend."""
    _persist_json_event_sync(category="backend_pending_auth_request", payload={})
    try:
        resp = httpx.post(f"{BACKEND_URL}/auth/pending", json={}, timeout=10.0)
        response_payload: dict[str, Any] = {
            "status_code": resp.status_code,
            "body": resp.text,
        }
        _persist_json_event_sync(category="backend_pending_auth_response", payload=response_payload)
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("token")
    except Exception as e:
        _persist_json_event_sync(category="backend_pending_auth_error", payload={"error": str(e)})
        logger.error(f"Failed to create pending: {e}")
    return None


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await _persist_json_event_async(
        category="telegram_update_start",
        payload=_safe_telegram_payload(update),
        update=update,
    )
    if not update.message:
        return

    user = update.effective_user
    args = context.args or []
    logger.info("User %s started with args: %s", getattr(user, "id", None), args)
    await send_miniapp_reply(update)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries."""
    await _persist_json_event_async(
        category="telegram_update_callback",
        payload=_safe_telegram_payload(update),
        update=update,
    )
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data or ""
    if data.startswith("login:"):
        token = data.replace("login:", "")
        user = query.from_user
        success = notify_backend_complete(token, user.id)
        if success:
            await query.edit_message_text("✅ Logged in!")
        else:
            await query.edit_message_text("❌ Failed")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _persist_json_event_async(
        category="telegram_update_help",
        payload=_safe_telegram_payload(update),
        update=update,
    )
    await send_miniapp_reply(update)


async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _persist_json_event_async(
        category="telegram_update_echo",
        payload=_safe_telegram_payload(update),
        update=update,
    )
    await send_miniapp_reply(update)


async def send_miniapp_reply(update: Update) -> None:
    """Reply with the mini app link."""
    if not update.message:
        return
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "Start your wealth journey 🤑",
                url=MINIAPP_URL,
                api_kwargs={"style": "success"},
            )
        ]]
    )
    await update.message.reply_text(
        "Trade xStocks on-chain with your Elite Council of AI Agents",
        reply_markup=keyboard,
    )


async def on_bot_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    update_payload = _safe_telegram_payload(update) if isinstance(update, Update) else {"raw_update_repr": repr(update)}
    await _persist_json_event_async(
        category="telegram_handler_error",
        payload={"update": update_payload, "error": str(context.error)},
        update=update if isinstance(update, Update) else None,
    )
    error = context.error
    if isinstance(error, Conflict):
        logger.error("Telegram polling conflict: another bot instance is already using getUpdates")
        return
    logger.exception("Unhandled Telegram bot error: %s", error)


def run_bot() -> None:
    if not BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set")
        return

    compatibility_error = _dependency_compatibility_error()
    if compatibility_error is not None:
        logger.error(compatibility_error)
        return

    logger.info("Starting bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_handler))
    app.add_error_handler(on_bot_error)

    logger.info("Bot polling...")
    try:
        app.run_polling(drop_pending_updates=True)
    except Conflict:
        logger.error("Bot exited: getUpdates conflict (ensure only one bot process is running)")


if __name__ == "__main__":
    run_bot()
