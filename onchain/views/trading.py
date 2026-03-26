from __future__ import annotations

from decimal import Decimal

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from wallet.models import TelegramIdentity
from wallet.views.base import error_response, json_response, parse_json, require_auth, run_sync

from ..services import OnchainConfigurationError, OnchainOrderService, OnchainStateError, OnchainWalletService


def _parse_positive_decimal(value: object, field_name: str) -> Decimal:
    if value is None:
        raise ValueError(f"{field_name} is required")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{field_name} is required")
    decimal_value = Decimal(str(value))
    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return decimal_value


def _get_first_present(data: dict, *keys: str) -> object:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _serialize_order(order) -> dict[str, str | int]:
    execution_details = order.execution_details if isinstance(order.execution_details, dict) else {}
    realized_pnl = Decimal(str(execution_details.get("realized_pnl", "0")))
    realized_pnl_percent = Decimal(str(execution_details.get("realized_pnl_percent", "0")))
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
        "offer_asset_id": order.offer_asset_id,
        "offer_amount": str(order.offer_amount),
        "receive_asset_id": order.receive_asset_id,
        "receive_amount": str(order.receive_amount),
        "tx_hash": order.tx_hash,
        "created_at": order.created_at.isoformat(),
    }


@method_decorator(csrf_exempt, name="dispatch")
class OnchainBuyView(View):
    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
            asset_id = str(data.get("asset_id") or "").strip()
            amount_value = _get_first_present(data, "amount_usdt", "amount")
            amount_usdt = _parse_positive_decimal(amount_value, "amount_usdt")
            if not asset_id:
                raise ValueError("asset_id is required")
        except (ValueError, ArithmeticError) as exc:
            return error_response(str(exc), 400)

        try:
            wallet = await run_sync(lambda: OnchainWalletService.require_wallet(identity))
            order = await OnchainOrderService.swap_usdt_to_asset(wallet, asset_id, amount_usdt)
        except (OnchainConfigurationError, OnchainStateError) as exc:
            return error_response(str(exc), 400)

        return json_response(_serialize_order(order))


@method_decorator(csrf_exempt, name="dispatch")
class OnchainSellView(View):
    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
            asset_id = str(data.get("asset_id") or "").strip()
            quantity_value = _get_first_present(
                data,
                "quantity",
                "amount",
                "qty",
                "shares",
                "asset_amount",
                "amount_asset",
                "stock_amount",
                "amount_stocks",
                "amount_shares",
                "quantity_shares",
                "amount_usdt",
            )
            quantity = _parse_positive_decimal(quantity_value, "quantity")
            if not asset_id:
                raise ValueError("asset_id is required")
        except (ValueError, ArithmeticError) as exc:
            return error_response(str(exc), 400)

        try:
            wallet = await run_sync(lambda: OnchainWalletService.require_wallet(identity))
            order = await OnchainOrderService.swap_asset_to_usdt(wallet, asset_id, quantity)
        except (OnchainConfigurationError, OnchainStateError) as exc:
            return error_response(str(exc), 400)

        return json_response(_serialize_order(order))


@method_decorator(csrf_exempt, name="dispatch")
class OnchainOrdersView(View):
    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            wallet = await run_sync(lambda: OnchainWalletService.require_wallet(identity))
        except OnchainStateError as exc:
            return error_response(str(exc), 404)
        orders = await run_sync(lambda: OnchainOrderService.get_orders(wallet))
        return json_response({"orders": [_serialize_order(order) for order in orders]})


@method_decorator(csrf_exempt, name="dispatch")
class OnchainOrderView(View):
    @require_auth
    async def get(
        self,
        request: HttpRequest,
        identity: TelegramIdentity,
        order_id: int,
    ) -> JsonResponse:
        try:
            wallet = await run_sync(lambda: OnchainWalletService.require_wallet(identity))
        except OnchainStateError as exc:
            return error_response(str(exc), 404)
        order = await run_sync(lambda: OnchainOrderService.get_order(wallet, order_id))
        if order is None:
            return error_response("Order not found", 404)
        return json_response(_serialize_order(order))
