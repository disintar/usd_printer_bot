"""Wallet TUI - A beautiful terminal UI for the custodial wallet service."""
from __future__ import annotations

from .api import WalletApi, ApiConfig
from .utils import format_decimal, mark_colored, MARK_COLORS
from .app import WalletTUI, run_tui

__all__ = [
    "WalletApi",
    "ApiConfig",
    "format_decimal",
    "mark_colored",
    "MARK_COLORS",
    "WalletTUI",
    "run_tui",
]
