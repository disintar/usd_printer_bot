"""Portfolio service for portfolio-level calculations and management."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ..models import AssetPosition, WalletAccount
from .prices import PricesService

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class PortfolioAsset:
    """Asset allocation within the portfolio."""

    asset_id: str
    quantity: Decimal
    value_usdt: Decimal
    allocation_percent: Decimal


@dataclass(frozen=True)
class PortfolioSummary:
    """Complete portfolio summary with PnL and allocation."""

    total_balance_usdt: Decimal
    pnl_percent: Decimal
    pnl_absolute: Decimal
    allocation: dict[str, float]
    assets: list[PortfolioAsset]


class PortfolioService:
    """Service for portfolio-level calculations and management."""

    @staticmethod
    def _calculate_equity(account: WalletAccount) -> Decimal:
        """Calculate total portfolio equity from cash and positions."""
        positions = list(AssetPosition.objects.filter(account=account))
        equity = account.cash_balance

        for position in positions:
            price = PricesService.get_price(position.asset_id)
            equity += position.quantity * price

        return equity

    @classmethod
    def get_portfolio(cls, account: WalletAccount) -> PortfolioSummary:
        """
        Get complete portfolio summary for an account.

        Includes total balance, PnL, and asset allocation.
        """
        equity = cls._calculate_equity(account)
        initial = account.initial_cash

        pnl_absolute = equity - initial
        pnl_percent = (pnl_absolute / initial * Decimal("100")) if initial > 0 else Decimal("0")

        # Calculate asset allocation
        portfolio_assets: list[PortfolioAsset] = []

        if account.cash_balance > 0:
            portfolio_assets.append(PortfolioAsset(
                asset_id="USDt",
                quantity=account.cash_balance,
                value_usdt=account.cash_balance,
                allocation_percent=Decimal("0"),
            ))

        positions = list(AssetPosition.objects.filter(account=account, quantity__gt=0))
        for position in positions:
            price = PricesService.get_price(position.asset_id)
            value = position.quantity * price

            allocation_percent = (value / equity * Decimal("100")) if equity > 0 else Decimal("0")

            portfolio_assets.append(PortfolioAsset(
                asset_id=position.asset_id,
                quantity=position.quantity,
                value_usdt=value,
                allocation_percent=allocation_percent.quantize(Decimal("0.01")),
            ))

        # Calculate cash allocation
        cash_allocation = (account.cash_balance / equity * 100) if equity > 0 else 0.0

        # Build allocation dict for agents
        allocation_dict: dict[str, float] = {}
        for asset in portfolio_assets:
            if asset.asset_id == "USDt":
                allocation_dict["USDt"] = float(cash_allocation)
            else:
                if asset.asset_id not in allocation_dict:
                    allocation_dict[asset.asset_id] = 0.0
                allocation_dict[asset.asset_id] += float(asset.allocation_percent)

        return PortfolioSummary(
            total_balance_usdt=equity.quantize(Decimal("0.01")),
            pnl_percent=pnl_percent.quantize(Decimal("0.01")),
            pnl_absolute=pnl_absolute.quantize(Decimal("0.01")),
            allocation=allocation_dict,
            assets=portfolio_assets,
        )

    @classmethod
    def rebalance(cls, account: WalletAccount) -> dict[str, list[dict]]:
        """
        Generate rebalancing actions to achieve target allocation.

        For test mode, returns mock actions based on current portfolio state.
        """
        portfolio = cls.get_portfolio(account)

        actions: list[dict] = []

        # Generate simple heuristic rebalancing suggestions
        for asset in portfolio.assets:
            if asset.asset_id == "USDt":
                continue

            # Mock: suggest buy if allocation is below target
            target_percent = 100.0 / (len(portfolio.assets) - 1) if len(portfolio.assets) > 1 else 100.0
            current_percent = float(asset.allocation_percent)

            if current_percent < target_percent * 0.8:
                actions.append({
                    "action": "buy",
                    "asset_id": asset.asset_id,
                    "reason": f"Underweight: {current_percent:.1f}% vs target {target_percent:.1f}%",
                })
            elif current_percent > target_percent * 1.2:
                actions.append({
                    "action": "sell",
                    "asset_id": asset.asset_id,
                    "reason": f"Overweight: {current_percent:.1f}% vs target {target_percent:.1f}%",
                })

        return {"actions": actions}

