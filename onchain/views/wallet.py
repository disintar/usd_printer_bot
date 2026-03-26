from __future__ import annotations

from decimal import Decimal

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from wallet.models import TelegramIdentity
from wallet.views.base import error_response, json_response, parse_json, require_auth, run_sync

from ..services import (
    OnchainBalanceService,
    OnchainConfigurationError,
    OnchainOrderService,
    OnchainStateError,
    OnchainWalletService,
)


def _parse_positive_decimal(value: object, field_name: str) -> Decimal:
    decimal_value = Decimal(str(value))
    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return decimal_value


@method_decorator(csrf_exempt, name="dispatch")
class OnchainWalletCreateView(View):
    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            wallet = await run_sync(lambda: OnchainWalletService.require_wallet(identity))
        except OnchainStateError:
            wallet = None

        if wallet is None:
            try:
                wallet = await OnchainWalletService.create_wallet(identity)
            except OnchainConfigurationError as exc:
                return error_response(str(exc), 503)

        return json_response(
            {
                "address": wallet.address,
                "version": wallet.version,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class OnchainDeployView(View):
    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            wallet = await run_sync(lambda: OnchainWalletService.require_wallet(identity))
            tx_hash = await OnchainWalletService.deploy_wallet(wallet)
        except (OnchainConfigurationError, OnchainStateError) as exc:
            return error_response(str(exc), 400)

        return json_response(
            {
                "address": wallet.address,
                "tx_hash": tx_hash,
                "status": "deployed",
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class OnchainAddressView(View):
    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            wallet = await run_sync(lambda: OnchainWalletService.require_wallet(identity))
        except OnchainStateError as exc:
            return error_response(str(exc), 404)
        return json_response({"address": wallet.address})


@method_decorator(csrf_exempt, name="dispatch")
class OnchainBalanceView(View):
    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            wallet = await run_sync(lambda: OnchainWalletService.require_wallet(identity))
        except OnchainStateError as exc:
            return error_response(str(exc), 404)
        try:
            balance = await OnchainBalanceService.get_balance(wallet)
        except OnchainConfigurationError as exc:
            return error_response(str(exc), 503)
        return json_response(
            {
                "cash_usdt": str(balance.cash_usdt),
                "equity_usdt": str(balance.equity_usdt),
                "total_balance_usdt": str(balance.total_balance_usdt),
                "pnl_percent": str(balance.pnl_percent),
                "pnl_absolute": str(balance.pnl_absolute),
                "assets": [
                    {
                        "asset_id": asset.asset_id,
                        "balance": str(asset.balance),
                        "current_price": str(asset.current_price),
                        "net_worth": str(asset.net_worth),
                        "pnl_percent": str(asset.pnl_percent),
                        "pnl_absolute": str(asset.pnl_absolute),
                        "allocation_percent": str(asset.allocation_percent),
                    }
                    for asset in balance.assets
                ],
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class OnchainWithdrawView(View):
    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
            amount = _parse_positive_decimal(data.get("amount_usdt"), "amount_usdt")
        except (ValueError, ArithmeticError) as exc:
            return error_response(str(exc), 400)

        destination_address = str(data.get("destination_address") or "").strip()
        if not destination_address:
            return error_response("destination_address is required", 400)

        try:
            wallet = await run_sync(lambda: OnchainWalletService.require_wallet(identity))
            order = await OnchainOrderService.withdraw_usdt(wallet, amount, destination_address)
        except (OnchainConfigurationError, OnchainStateError) as exc:
            return error_response(str(exc), 400)

        return json_response(
            {
                "order_id": order.id,
                "side": order.side,
                "asset_id": order.asset_id,
                "quantity": str(order.quantity),
                "price": str(order.price),
                "notional": str(order.notional),
                "status": order.status,
                "destination_address": order.destination_address,
                "tx_hash": order.tx_hash,
            }
        )
