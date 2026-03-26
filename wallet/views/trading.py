"""Trading views: assets, positions, buy, sell, orders."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from loguru import logger

from ..constants import TRADEABLE_ASSET_IDS
from ..models import TelegramIdentity
from ..services.assets import AssetsService
from ..services.orders import OrdersService
from ..services.positions import PositionsService
from ..services.prices import PricesService
from ..services.test_time_warp import TestTimeWarpService
from .base import (
    error_response,
    get_account_for_identity,
    json_response,
    parse_json,
    require_auth,
    run_sync,
)


def _format_utc_pretty(value: datetime) -> str:
    utc_value = value.astimezone(timezone.utc)
    return utc_value.strftime("%Y-%m-%d %H:%M UTC")


def _normalize_tradeable_asset_id(asset_id: object) -> str | None:
    asset = str(asset_id or "").strip()
    if not asset:
        return None
    for valid_asset in TRADEABLE_ASSET_IDS:
        if valid_asset.lower() == asset.lower():
            return valid_asset
    return None


async def _parse_quantity(data: dict[str, Any], asset_id: str) -> Decimal:
    quantity_raw = data.get("quantity")
    if quantity_raw is not None:
        try:
            return Decimal(str(quantity_raw))
        except InvalidOperation as exc:
            raise ValueError("Invalid quantity") from exc

    amount_usdt_raw = data.get("amount_usdt")
    if amount_usdt_raw is None:
        raise ValueError("quantity is required")

    try:
        amount_usdt = Decimal(str(amount_usdt_raw))
    except InvalidOperation as exc:
        raise ValueError("Invalid amount_usdt") from exc

    if amount_usdt <= 0:
        raise ValueError("amount_usdt must be positive")

    price = await run_sync(lambda: PricesService.get_price(asset_id))
    if price <= 0:
        raise ValueError("Asset price is unavailable")
    return amount_usdt / price


def _parse_positive_notional(data: dict[str, Any]) -> Decimal | None:
    amount_usdt_raw = data.get("amount_usdt")
    if amount_usdt_raw is None:
        return None
    try:
        amount_usdt = Decimal(str(amount_usdt_raw))
    except InvalidOperation as exc:
        raise ValueError("Invalid amount_usdt") from exc
    if amount_usdt <= 0:
        raise ValueError("amount_usdt must be positive")
    return amount_usdt


@method_decorator(csrf_exempt, name="dispatch")
class TestAssetsView(View):
    """GET /test/assets - List all supported assets with marks and PnL."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        started_at = time.perf_counter()
        request_id = str(request.META.get("HTTP_X_REQUEST_ID", "")).strip() or "-"
        logger.info(
            "TestAssetsView.get begin user_id={} request_id={} path={}",
            identity.telegram_user_id,
            request_id,
            request.path,
        )
        account = await get_account_for_identity(identity)
        if account is None:
            logger.warning(
                "TestAssetsView.get account_missing user_id={} request_id={} total_ms={}",
                identity.telegram_user_id,
                request_id,
                round((time.perf_counter() - started_at) * 1000),
            )
            return error_response("Account not found", 404)

        assets = await run_sync(lambda: AssetsService.get_all_assets(account))
        logger.info(
            "TestAssetsView.get success user_id={} request_id={} account_id={} assets={} total_ms={}",
            identity.telegram_user_id,
            request_id,
            account.id,
            len(assets),
            round((time.perf_counter() - started_at) * 1000),
        )
        return json_response(
            {
                "assets": [
                    {
                        "asset_id": asset.asset_id,
                        "balance": str(asset.balance),
                        "current_price": str(asset.current_price),
                        "net_worth": str(asset.net_worth),
                        "pnl_percent": str(asset.pnl_percent),
                        "pnl_absolute": str(asset.pnl_absolute),
                        "mark": asset.mark,
                    }
                    for asset in assets
                ]
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestAssetDetailView(View):
    """GET /test/asset/{id} - Get detailed asset information."""

    @require_auth
    async def get(
        self,
        request: HttpRequest,
        identity: TelegramIdentity,
        asset_id: str,
    ) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        detail = await run_sync(lambda: AssetsService.get_asset_detail(account, asset_id))
        if detail is None:
            return error_response(f"Asset '{asset_id}' not found", 404)

        return json_response(
            {
                "asset_id": detail.asset_id,
                "balance": str(detail.balance),
                "current_price": str(detail.current_price),
                "net_worth": str(detail.net_worth),
                "pnl_percent": str(detail.pnl_percent),
                "pnl_absolute": str(detail.pnl_absolute),
                "mark": detail.mark,
                "advisor_thought": detail.advisor_thought,
                "net_worth_chart": detail.net_worth_chart,
                "agent_marks": detail.agent_marks,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestPositionsView(View):
    """GET /test/positions - Get all open positions with marks."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        positions = await run_sync(lambda: PositionsService.get_all_positions(account))
        return json_response(
            {
                "positions": [
                    {
                        "asset_id": position.asset_id,
                        "quantity": str(position.quantity),
                        "average_entry_price": str(position.average_entry_price),
                        "current_price": str(position.current_price),
                        "net_worth": str(position.net_worth),
                        "pnl_percent": str(position.pnl_percent),
                        "pnl_absolute": str(position.pnl_absolute),
                        "mark": position.mark,
                        "advisor_thought": position.advisor_thought,
                    }
                    for position in positions
                ]
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestBuyView(View):
    """POST /test/buy - Place a buy order."""

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
        except ValueError:
            return error_response("Invalid JSON", 400)

        asset_id = _normalize_tradeable_asset_id(data.get("asset_id"))
        if asset_id is None:
            return error_response(
                f"Invalid asset_id. Must be one of: {', '.join(TRADEABLE_ASSET_IDS)}",
                400,
            )

        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        try:
            requested_notional = _parse_positive_notional(data)
            if requested_notional is not None:
                result = await run_sync(
                    lambda: OrdersService.create_buy_order_by_notional(
                        account,
                        asset_id,
                        requested_notional,
                    )
                )
            else:
                quantity = await _parse_quantity(data, asset_id)
                if quantity <= 0:
                    return error_response("Quantity must be positive", 400)
                result = await run_sync(lambda: OrdersService.create_buy_order(account, asset_id, quantity))
        except ValueError as exc:
            return error_response(str(exc), 400)

        return json_response(
            {
                "order_id": result.order_id,
                "side": result.side,
                "asset_id": result.asset_id,
                "quantity": str(result.quantity),
                "price": str(result.price),
                "notional": str(result.notional),
                "realized_pnl": str(result.realized_pnl.quantize(Decimal("0.01"))),
                "realized_pnl_percent": "0.00",
                "status": result.status,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestSellView(View):
    """POST /test/sell - Place a sell order."""

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
        except ValueError:
            return error_response("Invalid JSON", 400)

        asset_id = _normalize_tradeable_asset_id(data.get("asset_id"))
        if asset_id is None:
            return error_response(
                f"Invalid asset_id. Must be one of: {', '.join(TRADEABLE_ASSET_IDS)}",
                400,
            )

        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        try:
            requested_notional = _parse_positive_notional(data)
            if requested_notional is not None:
                result = await run_sync(
                    lambda: OrdersService.create_sell_order_by_notional(
                        account,
                        asset_id,
                        requested_notional,
                    )
                )
            else:
                quantity = await _parse_quantity(data, asset_id)
                if quantity <= 0:
                    return error_response("Quantity must be positive", 400)
                result = await run_sync(lambda: OrdersService.create_sell_order(account, asset_id, quantity))
        except ValueError as exc:
            return error_response(str(exc), 400)

        realized_cost = result.notional - result.realized_pnl
        realized_pnl_percent = (
            (result.realized_pnl / realized_cost) * Decimal("100")
            if realized_cost > 0
            else Decimal("0")
        )
        return json_response(
            {
                "order_id": result.order_id,
                "side": result.side,
                "asset_id": result.asset_id,
                "quantity": str(result.quantity),
                "price": str(result.price),
                "notional": str(result.notional),
                "realized_pnl": str(result.realized_pnl.quantize(Decimal("0.01"))),
                "realized_pnl_percent": str(realized_pnl_percent.quantize(Decimal("0.01"))),
                "status": result.status,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestOrderView(View):
    """GET /test/order/{id} - Get a specific order."""

    @require_auth
    async def get(
        self,
        request: HttpRequest,
        identity: TelegramIdentity,
        order_id: int,
    ) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        order = await run_sync(lambda: OrdersService.get_order(account, order_id))
        if order is None:
            return error_response("Order not found", 404)

        realized_pnl = order.realized_pnl if order.realized_pnl is not None else Decimal("0")
        realized_cost = order.notional - realized_pnl
        realized_pnl_percent = (
            (realized_pnl / realized_cost) * Decimal("100")
            if order.side == "sell" and realized_cost > 0
            else Decimal("0")
        )
        return json_response(
            {
                "order_id": order.id,
                "side": order.side,
                "asset_id": order.asset_id,
                "quantity": str(order.quantity),
                "price": str(order.price),
                "notional": str(order.notional),
                "realized_pnl": str(realized_pnl.quantize(Decimal("0.01"))),
                "realized_pnl_percent": str(realized_pnl_percent.quantize(Decimal("0.01"))),
                "status": order.status,
                "created_at": order.created_at.isoformat(),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestOrdersView(View):
    """GET /test/orders - Get all orders."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        started_at = time.perf_counter()
        request_id = str(request.META.get("HTTP_X_REQUEST_ID", "")).strip() or "-"
        logger.info(
            "TestOrdersView.get begin user_id={} request_id={} path={}",
            identity.telegram_user_id,
            request_id,
            request.path,
        )
        account = await get_account_for_identity(identity)
        if account is None:
            logger.warning(
                "TestOrdersView.get account_missing user_id={} request_id={} total_ms={}",
                identity.telegram_user_id,
                request_id,
                round((time.perf_counter() - started_at) * 1000),
            )
            return error_response("Account not found", 404)

        load_started_at = time.perf_counter()
        orders = await run_sync(lambda: OrdersService.get_all_orders(account))
        load_ms = round((time.perf_counter() - load_started_at) * 1000)
        def _serialize_order(order: Any) -> dict[str, object]:
            realized_pnl = order.realized_pnl if order.realized_pnl is not None else Decimal("0")
            realized_cost = order.notional - realized_pnl
            realized_pnl_percent = (
                (realized_pnl / realized_cost) * Decimal("100")
                if order.side == "sell" and realized_cost > 0
                else Decimal("0")
            )
            return {
                "order_id": order.id,
                "side": order.side,
                "asset_id": order.asset_id,
                "quantity": str(order.quantity),
                "price": str(order.price),
                "notional": str(order.notional),
                "realized_pnl": str(realized_pnl.quantize(Decimal("0.01"))),
                "realized_pnl_percent": str(realized_pnl_percent.quantize(Decimal("0.01"))),
                "status": order.status,
                "created_at": order.created_at.isoformat(),
            }

        serialize_started_at = time.perf_counter()
        serialized_orders = [_serialize_order(order) for order in orders]
        serialize_ms = round((time.perf_counter() - serialize_started_at) * 1000)
        logger.info(
            "TestOrdersView.get success user_id={} request_id={} account_id={} orders={} load_ms={} serialize_ms={} total_ms={}",
            identity.telegram_user_id,
            request_id,
            account.id,
            len(serialized_orders),
            load_ms,
            serialize_ms,
            round((time.perf_counter() - started_at) * 1000),
        )
        return json_response(
            {
                "orders": serialized_orders
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestPricesView(View):
    """GET /test/prices - Get all asset prices."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        prices = await run_sync(PricesService.get_all_prices)
        clock = await run_sync(TestTimeWarpService.get_clock_info)
        return json_response({
            "prices": {asset_id: str(price) for asset_id, price in prices.items()},
            "server_time_utc": clock.real_now.isoformat(),
            "server_time_utc_pretty": _format_utc_pretty(clock.real_now),
            "simulated_time_utc": clock.simulated_now.isoformat(),
            "simulated_time_utc_pretty": _format_utc_pretty(clock.simulated_now),
        })
