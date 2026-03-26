"""Utility functions for TUI."""
from __future__ import annotations

from decimal import Decimal
from typing import Union

# Mark colors
MARK_COLORS: dict[str, str] = {
    "Buy": "green",
    "Cover": "cyan",
    "Sell": "red",
    "Short": "magenta",
    "Hold": "yellow",
}


def format_decimal(value: Union[str, float, Decimal], places: int = 2) -> str:
    """Format decimal value for display."""
    try:
        d = Decimal(str(value))
        return f"{d:,.{places}f}"
    except Exception:
        return str(value)


def mark_colored(mark: str) -> str:
    """Return colored mark string."""
    color = MARK_COLORS.get(mark, "white")
    return f"[{color}]{mark}[/{color}]"
