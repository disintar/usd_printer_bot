"""Positions service for managing and retrieving asset positions."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ..models import AssetPosition, WalletAccount
from .advisor_marks import AdvisorMarksService
from .market_signals import MarketSignalsService
from .prices import PricesService

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class PositionInfo:
    """Position information with balance, PnL, and AI agent mark."""

    asset_id: str
    quantity: Decimal
    average_entry_price: Decimal
    current_price: Decimal
    net_worth: Decimal
    pnl_percent: Decimal
    pnl_absolute: Decimal
    mark: str
    advisor_thought: str


class PositionsService:
    """Service for managing and retrieving asset positions."""

    @classmethod
    def _calculate_position_pnl(
        cls,
        position: AssetPosition,
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate PnL for a position.

        Returns (pnl_percent, pnl_absolute).
        """
        if position.average_entry_price <= 0 or position.quantity <= 0:
            return Decimal("0"), Decimal("0")

        current_price = PricesService.get_price(position.asset_id)
        entry_value = position.average_entry_price * position.quantity
        current_value = current_price * position.quantity

        pnl_absolute = current_value - entry_value

        if entry_value > 0:
            pnl_percent = (pnl_absolute / entry_value) * Decimal("100")
        else:
            pnl_percent = Decimal("0")

        return pnl_percent, pnl_absolute

    @classmethod
    def get_all_positions(cls, account: WalletAccount) -> list[PositionInfo]:
        """Get all non-zero positions for an account."""
        positions = list(AssetPosition.objects.filter(account=account, quantity__gt=0))
        asset_ids = [position.asset_id for position in positions]
        marks = MarketSignalsService.safe_asset_marks(asset_ids)
        advisor_insights = AdvisorMarksService.get_marks_and_thoughts(account)

        result = []
        for position in positions:
            current_price = PricesService.get_price(position.asset_id)
            net_worth = position.quantity * current_price
            pnl_percent, pnl_absolute = cls._calculate_position_pnl(position)
            mark = advisor_insights.marks.get(position.asset_id, marks.get(position.asset_id, "Hold"))
            advisor_thought = advisor_insights.thoughts.get(position.asset_id, "")

            result.append(PositionInfo(
                asset_id=position.asset_id,
                quantity=position.quantity,
                average_entry_price=position.average_entry_price,
                current_price=current_price,
                net_worth=net_worth,
                pnl_percent=pnl_percent.quantize(Decimal("0.01")),
                pnl_absolute=pnl_absolute.quantize(Decimal("0.01")),
                mark=mark,
                advisor_thought=advisor_thought,
            ))

        return result

    @classmethod
    def get_position(cls, account: WalletAccount, asset_id: str) -> PositionInfo | None:
        """Get a specific position by asset ID."""
        try:
            position = AssetPosition.objects.get(account=account, asset_id=asset_id, quantity__gt=0)
        except AssetPosition.DoesNotExist:
            return None

        current_price = PricesService.get_price(asset_id)
        net_worth = position.quantity * current_price
        pnl_percent, pnl_absolute = cls._calculate_position_pnl(position)
        market_mark = MarketSignalsService.safe_asset_marks([asset_id]).get(asset_id, "Hold")
        advisor_insights = AdvisorMarksService.get_marks_and_thoughts(account)
        mark = advisor_insights.marks.get(asset_id, market_mark)
        advisor_thought = advisor_insights.thoughts.get(asset_id, "")

        return PositionInfo(
            asset_id=position.asset_id,
            quantity=position.quantity,
            average_entry_price=position.average_entry_price,
            current_price=current_price,
            net_worth=net_worth,
            pnl_percent=pnl_percent.quantize(Decimal("0.01")),
            pnl_absolute=pnl_absolute.quantize(Decimal("0.01")),
            mark=mark,
            advisor_thought=advisor_thought,
        )
