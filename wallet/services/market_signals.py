from __future__ import annotations

import asyncio
from decimal import Decimal
import time

from loguru import logger

from ..constants import AGENT_IDS
from .financial_mcp import FinancialMcpError, FinancialMcpService


class MarketSignalsService:
    """Derives simple recommendation marks from MCP market snapshots."""

    @classmethod
    def get_asset_marks(cls, asset_ids: list[str]) -> dict[str, str]:
        """Return a top-level mark for each asset."""
        started_at = time.perf_counter()
        logger.info(
            "market_signals.get_asset_marks begin assets_count={}",
            len(asset_ids),
        )
        try:
            snapshots = asyncio.run(FinancialMcpService.list_market_snapshots(asset_ids))
        except FinancialMcpError:
            logger.warning(
                "market_signals.get_asset_marks fallback assets_count={} total_ms={}",
                len(asset_ids),
                round((time.perf_counter() - started_at) * 1000),
            )
            return {asset_id: "Hold" for asset_id in asset_ids}
        logger.info(
            "market_signals.get_asset_marks success assets_count={} snapshots={} total_ms={}",
            len(asset_ids),
            len(snapshots),
            round((time.perf_counter() - started_at) * 1000),
        )
        return {snapshot.asset_id: cls._classify_asset(snapshot.upside_percent) for snapshot in snapshots}

    @classmethod
    def get_agent_marks_for_asset(cls, asset_id: str) -> dict[str, str]:
        """Return agent-flavored marks for a single asset."""
        started_at = time.perf_counter()
        try:
            snapshots = asyncio.run(FinancialMcpService.list_market_snapshots([asset_id]))
            snapshot = snapshots[0]
        except (FinancialMcpError, IndexError):
            logger.warning(
                "market_signals.get_agent_marks_for_asset fallback asset_id={} total_ms={}",
                asset_id,
                round((time.perf_counter() - started_at) * 1000),
            )
            return {agent_id: "Hold" for agent_id in AGENT_IDS}
        upside_percent = snapshot.upside_percent
        logger.info(
            "market_signals.get_agent_marks_for_asset success asset_id={} upside_percent={} total_ms={}",
            asset_id,
            upside_percent.quantize(Decimal("0.01")),
            round((time.perf_counter() - started_at) * 1000),
        )
        return {
            "Buy": "Buy" if upside_percent >= Decimal("12") else "Hold",
            "Cover": "Cover" if upside_percent <= Decimal("0") else "Hold",
            "Sell": "Sell" if upside_percent <= Decimal("-8") else "Hold",
            "Short": "Short" if upside_percent <= Decimal("-15") else "Hold",
            "Hold": "Hold",
        }

    @classmethod
    def safe_asset_marks(cls, asset_ids: list[str]) -> dict[str, str]:
        """Return MCP-driven marks with a conservative fallback."""
        try:
            return cls.get_asset_marks(asset_ids)
        except FinancialMcpError:
            return {asset_id: "Hold" for asset_id in asset_ids}

    @classmethod
    def safe_agent_marks_for_asset(cls, asset_id: str) -> dict[str, str]:
        """Return MCP-driven agent marks with a conservative fallback."""
        try:
            return cls.get_agent_marks_for_asset(asset_id)
        except FinancialMcpError:
            return {agent_id: "Hold" for agent_id in AGENT_IDS}

    @staticmethod
    def _classify_asset(upside_percent: Decimal) -> str:
        if upside_percent >= Decimal("15"):
            return "Buy"
        if upside_percent <= Decimal("-8"):
            return "Sell"
        return "Hold"
