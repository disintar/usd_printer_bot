"""Tests for Telegram bot."""
from __future__ import annotations


class TestBotImports:
    def test_bot_module_loads(self):
        from bot.telegram_bot import run_bot
        assert callable(run_bot)
    
    def test_notify_backend_complete_exists(self):
        from bot.telegram_bot import notify_backend_complete
        assert callable(notify_backend_complete)
    
    def test_create_pending_auth_exists(self):
        from bot.telegram_bot import create_pending_auth
        assert callable(create_pending_auth)
