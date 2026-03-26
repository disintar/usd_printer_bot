"""Terminal compatibility helpers for Textual runtime quirks."""
from __future__ import annotations

import os
from typing import Any

from textual.drivers.linux_driver import LinuxDriver
from textual.drivers.linux_inline_driver import LinuxInlineDriver


class TerminalCompatibilityService:
    """Apply compatibility patches for terminals that leak query bytes."""

    _patched: bool = False

    @classmethod
    def apply(cls) -> None:
        """Disable noisy terminal capability probes unless explicitly enabled."""
        if cls._patched:
            return
        if not cls._should_disable_terminal_queries():
            return

        LinuxDriver._request_terminal_sync_mode_support = cls._noop_terminal_query
        LinuxDriver._query_in_band_window_resize = cls._noop_terminal_query
        LinuxInlineDriver._request_terminal_sync_mode_support = cls._noop_terminal_query
        LinuxInlineDriver._query_in_band_window_resize = cls._noop_terminal_query
        cls._patched = True

    @staticmethod
    def _should_disable_terminal_queries() -> bool:
        value = os.getenv("TUI_ENABLE_TERMINAL_QUERIES", "").strip().lower()
        return value not in {"1", "true", "yes", "on"}

    @staticmethod
    def _noop_terminal_query(self: Any) -> None:
        """Intentionally no-op to avoid writing unsupported `$p` queries."""
        return None
