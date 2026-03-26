"""Assets service for asset information and marks."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import time
from typing import TYPE_CHECKING

from loguru import logger

from ..constants import SUPPORTED_ASSET_IDS
from ..models import AssetPosition, WalletAccount
from .advisor_marks import AdvisorMarksService
from .market_signals import MarketSignalsService
from .prices import PricesService

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class AssetInfo:
    """Asset information with balance and PnL."""

    asset_id: str
    balance: Decimal
    current_price: Decimal
    net_worth: Decimal
    pnl_percent: Decimal
    pnl_absolute: Decimal
    mark: str


@dataclass(frozen=True)
class AssetDetail:
    """Detailed asset information for the detail screen."""

    asset_id: str
    balance: Decimal
    current_price: Decimal
    net_worth: Decimal
    pnl_percent: Decimal
    pnl_absolute: Decimal
    mark: str
    advisor_thought: str
    net_worth_chart: list[dict]
    agent_marks: dict[str, str]


class AssetsService:
    """Service for asset information and marks."""

    @staticmethod
    def _generate_net_worth_chart(asset_id: str, current_price: Decimal) -> list[dict]:
        """Return persisted historical price chart for an asset."""
        return PricesService.get_price_history(asset_id, days=30)

    @staticmethod
    def _calculate_position_pnl(position: AssetPosition) -> tuple[Decimal, Decimal]:
        """
        Calculate PnL for a position.

        Returns (pnl_percent, pnl_absolute).
        """
        if position.average_entry_price <= 0:
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
    def get_all_assets(cls, account: WalletAccount) -> list[AssetInfo]:
        """Get all supported assets with current balances and marks."""
        started_at = time.perf_counter()
        logger.info(
            "assets.get_all_assets begin account_id={} supported_assets={}",
            account.id,
            len(SUPPORTED_ASSET_IDS),
        )

        stage_started_at = time.perf_counter()
        positions = {p.asset_id: p for p in AssetPosition.objects.filter(account=account)}
        positions_ms = round((time.perf_counter() - stage_started_at) * 1000)

        stage_started_at = time.perf_counter()
        marks = MarketSignalsService.safe_asset_marks(list(SUPPORTED_ASSET_IDS))
        marks_ms = round((time.perf_counter() - stage_started_at) * 1000)

        logger.info(
            "assets.get_all_assets dependencies account_id={} positions={} positions_ms={} market_marks={} market_marks_ms={}",
            account.id,
            len(positions),
            positions_ms,
            len(marks),
            marks_ms,
        )

        stage_started_at = time.perf_counter()
        assets = []
        for asset_id in SUPPORTED_ASSET_IDS:
            position = positions.get(asset_id)
            balance = position.quantity if position else Decimal("0")
            current_price = PricesService.get_price(asset_id)
            net_worth = balance * current_price

            if position and position.average_entry_price > 0:
                pnl_percent, pnl_absolute = cls._calculate_position_pnl(position)
            else:
                pnl_percent = Decimal("0")
                pnl_absolute = Decimal("0")

            mark = marks.get(asset_id, "Hold")

            assets.append(AssetInfo(
                asset_id=asset_id,
                balance=balance,
                current_price=current_price,
                net_worth=net_worth,
                pnl_percent=pnl_percent.quantize(Decimal("0.01")),
                pnl_absolute=pnl_absolute.quantize(Decimal("0.01")),
                mark=mark,
            ))

        assemble_ms = round((time.perf_counter() - stage_started_at) * 1000)
        logger.info(
            "assets.get_all_assets success account_id={} assets={} assemble_ms={} total_ms={}",
            account.id,
            len(assets),
            assemble_ms,
            round((time.perf_counter() - started_at) * 1000),
        )
        return assets

    @classmethod
    def get_asset_detail(cls, account: WalletAccount, asset_id: str) -> AssetDetail | None:
        """Get detailed information for a specific asset."""
        if asset_id not in SUPPORTED_ASSET_IDS:
            return None

        current_price = PricesService.get_price(asset_id)

        try:
            position = AssetPosition.objects.get(account=account, asset_id=asset_id)
            balance = position.quantity
        except AssetPosition.DoesNotExist:
            balance = Decimal("0")

        net_worth = balance * current_price

        if balance > 0:
            try:
                position = AssetPosition.objects.get(account=account, asset_id=asset_id)
                if position.average_entry_price > 0:
                    pnl_percent, pnl_absolute = cls._calculate_position_pnl(position)
                else:
                    pnl_percent = Decimal("0")
                    pnl_absolute = Decimal("0")
            except AssetPosition.DoesNotExist:
                pnl_percent = Decimal("0")
                pnl_absolute = Decimal("0")
        else:
            pnl_percent = Decimal("0")
            pnl_absolute = Decimal("0")

        market_mark = MarketSignalsService.safe_asset_marks([asset_id]).get(asset_id, "Hold")
        advisor_insights = AdvisorMarksService.get_marks_and_thoughts(account)
        mark = advisor_insights.marks.get(asset_id, market_mark)
        advisor_thought = advisor_insights.thoughts.get(asset_id, "")
        net_worth_chart = cls._generate_net_worth_chart(asset_id, current_price)
        agent_marks = MarketSignalsService.safe_agent_marks_for_asset(asset_id)

        return AssetDetail(
            asset_id=asset_id,
            balance=balance,
            current_price=current_price,
            net_worth=net_worth,
            pnl_percent=pnl_percent.quantize(Decimal("0.01")),
            pnl_absolute=pnl_absolute.quantize(Decimal("0.01")),
            mark=mark,
            advisor_thought=advisor_thought,
            net_worth_chart=net_worth_chart,
            agent_marks=agent_marks,
        )
