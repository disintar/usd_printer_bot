"""Async financial MCP service for quote and analyst recommendation data."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from decimal import Decimal

import httpx
from django.conf import settings
from loguru import logger

from ..constants import TRADEABLE_ASSET_IDS
from .prices import PricesService


class FinancialMcpError(ValueError):
    """Raised when the MCP endpoint is unavailable or returns invalid data."""


@dataclass(frozen=True)
class MarketSnapshot:
    """Normalized market snapshot from the financial MCP."""

    asset_id: str
    symbol: str
    price: Decimal
    target_consensus: Decimal | None
    target_high: Decimal | None
    target_low: Decimal | None

    @property
    def upside_percent(self) -> Decimal:
        if self.target_consensus is None or self.price <= 0:
            return Decimal("0")
        return ((self.target_consensus - self.price) / self.price) * Decimal("100")


class FinancialMcpService:
    """Stateful MCP client for quote and analyst recommendation data."""

    @classmethod
    async def list_market_snapshots(cls, asset_ids: list[str]) -> list[MarketSnapshot]:
        """Fetch quote and analyst target data for tradeable assets."""
        if not getattr(settings, "MCP_ENABLED", False):
            raise FinancialMcpError("MCP is disabled")
        server_url = str(getattr(settings, "MCP_SERVER_URL", "")).strip()
        if not server_url:
            raise FinancialMcpError("MCP_SERVER_URL is not configured")

        started_at = time.perf_counter()
        logger.info(
            "mcp.list_market_snapshots begin assets_count={} assets={}",
            len(asset_ids),
            ",".join(asset_ids),
        )
        snapshots: list[MarketSnapshot] = []
        try:
            async with httpx.AsyncClient(timeout=float(getattr(settings, "MCP_TIMEOUT_SECONDS", 10.0))) as client:
                session_id = await cls._initialize_session(client, server_url)
                await cls._enable_toolset(client, server_url, session_id, "quotes")
                await cls._enable_toolset(client, server_url, session_id, "analyst")

                for asset_id in asset_ids:
                    symbol = cls._symbol_for_asset(asset_id)
                    quote_payload = await cls._call_tool(client, server_url, session_id, "getQuote", {"symbol": symbol})
                    target_payload = await cls._call_tool(
                        client,
                        server_url,
                        session_id,
                        "getPriceTargetConsensus",
                        {"symbol": symbol},
                    )
                    snapshots.append(cls._build_snapshot(asset_id, symbol, quote_payload, target_payload))
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
            raise FinancialMcpError(str(exc)) from exc
        logger.info(
            "mcp.list_market_snapshots success assets_count={} total_ms={}",
            len(snapshots),
            round((time.perf_counter() - started_at) * 1000),
        )
        return snapshots

    @classmethod
    async def _initialize_session(cls, client: httpx.AsyncClient, server_url: str) -> str:
        started_at = time.perf_counter()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": getattr(settings, "MCP_PROTOCOL_VERSION", "2025-03-26"),
                "capabilities": {},
                "clientInfo": {"name": "dbablo", "version": "1.0"},
            },
        }
        response = await client.post(
            server_url,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            json=payload,
        )
        response.raise_for_status()
        session_id = response.headers.get("mcp-session-id", "").strip()
        if not session_id:
            raise FinancialMcpError("MCP session id is missing")
        logger.info(
            "mcp._initialize_session success total_ms={}",
            round((time.perf_counter() - started_at) * 1000),
        )
        return session_id

    @classmethod
    async def _enable_toolset(
        cls,
        client: httpx.AsyncClient,
        server_url: str,
        session_id: str,
        toolset_name: str,
    ) -> None:
        started_at = time.perf_counter()
        await cls._call_rpc(
            client,
            server_url,
            session_id,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "enable_toolset",
                    "arguments": {"name": toolset_name},
                },
            },
        )
        logger.info(
            "mcp._enable_toolset success toolset={} total_ms={}",
            toolset_name,
            round((time.perf_counter() - started_at) * 1000),
        )

    @classmethod
    async def _call_tool(
        cls,
        client: httpx.AsyncClient,
        server_url: str,
        session_id: str,
        tool_name: str,
        arguments: dict[str, str],
    ) -> list[dict[str, object]]:
        started_at = time.perf_counter()
        rpc_payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        response_payload = await cls._call_rpc(client, server_url, session_id, rpc_payload)
        content = response_payload.get("result", {}).get("content", [])
        if not isinstance(content, list) or not content:
            raise FinancialMcpError(f"MCP tool '{tool_name}' returned empty content")
        tool_text = content[0].get("text", "")
        if not isinstance(tool_text, str):
            raise FinancialMcpError(f"MCP tool '{tool_name}' returned invalid text payload")
        decoded = json.loads(tool_text)
        if not isinstance(decoded, list):
            raise FinancialMcpError(f"MCP tool '{tool_name}' returned invalid data format")
        logger.info(
            "mcp._call_tool success tool_name={} symbol={} rows={} total_ms={}",
            tool_name,
            arguments.get("symbol", ""),
            len(decoded),
            round((time.perf_counter() - started_at) * 1000),
        )
        return decoded

    @classmethod
    async def _call_rpc(
        cls,
        client: httpx.AsyncClient,
        server_url: str,
        session_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        started_at = time.perf_counter()
        response = await client.post(
            server_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": session_id,
            },
            json=payload,
        )
        response.raise_for_status()
        data_line = cls._extract_data_line(response.text)
        decoded = json.loads(data_line)
        if "error" in decoded:
            raise FinancialMcpError(str(decoded["error"]))
        logger.info(
            "mcp._call_rpc success method={} total_ms={}",
            payload.get("method", ""),
            round((time.perf_counter() - started_at) * 1000),
        )
        return decoded

    @staticmethod
    def _extract_data_line(response_text: str) -> str:
        for line in response_text.splitlines():
            if line.startswith("data: "):
                return line[6:]
        raise FinancialMcpError("MCP response did not contain a data line")

    @staticmethod
    def _symbol_for_asset(asset_id: str) -> str:
        symbol = PricesService.FMP_SYMBOL_BY_ASSET.get(asset_id)
        if symbol is None or asset_id not in TRADEABLE_ASSET_IDS:
            raise FinancialMcpError(f"Unsupported asset for MCP lookup: {asset_id}")
        return symbol

    @staticmethod
    def _build_snapshot(
        asset_id: str,
        symbol: str,
        quote_payload: list[dict[str, object]],
        target_payload: list[dict[str, object]],
    ) -> MarketSnapshot:
        if not quote_payload:
            raise FinancialMcpError(f"Missing quote payload for {symbol}")
        quote_row = quote_payload[0]
        target_row = target_payload[0] if target_payload else {}

        price = Decimal(str(quote_row["price"]))
        target_consensus = FinancialMcpService._optional_decimal(target_row.get("targetConsensus"))
        target_high = FinancialMcpService._optional_decimal(target_row.get("targetHigh"))
        target_low = FinancialMcpService._optional_decimal(target_row.get("targetLow"))

        return MarketSnapshot(
            asset_id=asset_id,
            symbol=symbol,
            price=price,
            target_consensus=target_consensus,
            target_high=target_high,
            target_low=target_low,
        )

    @staticmethod
    def _optional_decimal(value: object) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))
