"""Wallet summary service for calculating wallet balance and PnL."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ..models import AssetPosition, WalletAccount
from .prices import PricesService

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class WalletBalance:
    """Complete wallet balance information with PnL."""

    cash_usdt: Decimal
    equity_usdt: Decimal
    total_balance_usdt: Decimal
    pnl_percent: Decimal
    pnl_absolute: Decimal


class WalletSummaryService:
    """Service for calculating wallet summaries and PnL."""

    @staticmethod
    def _calculate_equity(account: WalletAccount) -> Decimal:
        """Calculate total equity from cash and positions."""
        positions = AssetPosition.objects.filter(account=account)
        equity = account.cash_balance

        for position in positions:
            price = PricesService.get_price(position.asset_id)
            equity += position.quantity * price

        return equity

    @staticmethod
    def _calculate_pnl(account: WalletAccount) -> tuple[Decimal, Decimal]:
        """
        Calculate unrealized PnL absolute and percent across all open positions.

        Returns (pnl_absolute, pnl_percent).
        """
        positions = AssetPosition.objects.filter(account=account)
        total_entry_value = Decimal("0")
        total_pnl_absolute = Decimal("0")

        for position in positions:
            entry_value = position.quantity * position.average_entry_price
            current_value = position.quantity * PricesService.get_price(position.asset_id)
            total_entry_value += entry_value
            total_pnl_absolute += current_value - entry_value

        if total_entry_value > 0:
            pnl_percent = (total_pnl_absolute / total_entry_value) * Decimal("100")
        else:
            pnl_percent = Decimal("0")

        return total_pnl_absolute, pnl_percent

    @classmethod
    def get_balance(cls, account: WalletAccount) -> WalletBalance:
        """Get complete balance for a wallet account."""
        cash = account.cash_balance
        equity = cls._calculate_equity(account)
        total = equity
        pnl_absolute, pnl_percent = cls._calculate_pnl(account)

        return WalletBalance(
            cash_usdt=cash,
            equity_usdt=equity,
            total_balance_usdt=total,
            pnl_percent=pnl_percent.quantize(Decimal("0.01")),
            pnl_absolute=pnl_absolute.quantize(Decimal("0.01")),
        )
