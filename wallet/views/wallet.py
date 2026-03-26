"""Wallet management views: balance, deposit, withdraw, transfer, address."""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from ..models import TelegramIdentity, WalletAccount
from ..services.test_time_warp import TestTimeWarpService
from ..services.wallet_summary import WalletSummaryService
from .base import (
    error_response,
    generate_deterministic_address,
    get_account_for_identity,
    json_response,
    parse_json,
    require_auth,
    run_sync,
    validate_positive_decimal,
)

TEST_MODE_MAX_DEPOSIT_USDT = Decimal("1000")


def _format_utc_pretty(value: datetime) -> str:
    utc_value = value.astimezone(timezone.utc)
    return utc_value.strftime("%Y-%m-%d %H:%M UTC")


def _apply_deposit(account: WalletAccount, amount: Decimal) -> Decimal:
    account.cash_balance += amount
    account.net_cash_flow += amount
    account.save(update_fields=["cash_balance", "net_cash_flow", "updated_at"])
    return account.cash_balance


def _apply_withdraw(account: WalletAccount, amount: Decimal) -> Decimal:
    account.cash_balance -= amount
    account.net_cash_flow -= amount
    account.save(update_fields=["cash_balance", "net_cash_flow", "updated_at"])
    return account.cash_balance


def _apply_transfer(
    from_account: WalletAccount,
    to_telegram_user_id: int,
    amount: Decimal,
) -> Decimal | None:
    try:
        to_identity = TelegramIdentity.objects.get(telegram_user_id=to_telegram_user_id)
        to_account = to_identity.account
    except TelegramIdentity.DoesNotExist:
        return None

    from_account.cash_balance -= amount
    from_account.save(update_fields=["cash_balance", "updated_at"])

    to_account.cash_balance += amount
    to_account.net_cash_flow += amount
    to_account.save(update_fields=["cash_balance", "net_cash_flow", "updated_at"])

    return from_account.cash_balance


@method_decorator(csrf_exempt, name="dispatch")
class TestBalanceView(View):
    """GET /test/balance - Get wallet balance with PnL."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        balance = await run_sync(lambda: WalletSummaryService.get_balance(account))
        return json_response(
            {
                "cash_usdt": str(balance.cash_usdt),
                "equity_usdt": str(balance.equity_usdt),
                "total_balance_usdt": str(balance.total_balance_usdt),
                "pnl_percent": str(balance.pnl_percent),
                "pnl_absolute": str(balance.pnl_absolute),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestAddressView(View):
    """GET /test/address - Get deterministic test address for user."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        address = generate_deterministic_address(identity.telegram_user_id)
        return json_response({"address": address})


@method_decorator(csrf_exempt, name="dispatch")
class TestTimeView(View):
    """GET /test/time - Get backend real and simulated test-mode clock."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        clock = await run_sync(TestTimeWarpService.get_clock_info)
        return json_response(
            {
                "server_time_utc": clock.real_now.isoformat(),
                "server_time_utc_pretty": _format_utc_pretty(clock.real_now),
                "simulated_time_utc": clock.simulated_now.isoformat(),
                "simulated_time_utc_pretty": _format_utc_pretty(clock.simulated_now),
                "test_time_warp_enabled": clock.enabled,
                "window_days": clock.window_days,
                "hours_per_tick": clock.hours_per_tick,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestDepositView(View):
    """POST /test/deposit - Deposit USDt to wallet."""

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
        except ValueError:
            return error_response("Invalid JSON", 400)

        amount_value = data.get("amount")
        if amount_value is None:
            amount_value = data.get("amount_usdt")

        try:
            amount = validate_positive_decimal(amount_value, "amount")
        except ValueError as exc:
            return error_response(str(exc), 400)
        if amount > TEST_MODE_MAX_DEPOSIT_USDT:
            return error_response(
                f"amount exceeds test-mode limit ({TEST_MODE_MAX_DEPOSIT_USDT} USDt)",
                400,
            )

        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        new_balance = await run_sync(lambda: _apply_deposit(account, amount))
        return json_response(
            {
                "deposited": str(amount),
                "new_balance": str(new_balance),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestWithdrawView(View):
    """POST /test/withdraw - Withdraw USDt from wallet."""

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
        except ValueError:
            return error_response("Invalid JSON", 400)

        amount_value = data.get("amount")
        if amount_value is None:
            amount_value = data.get("amount_usdt")

        try:
            amount = validate_positive_decimal(amount_value, "amount")
        except ValueError as exc:
            return error_response(str(exc), 400)

        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        if account.cash_balance < amount:
            return error_response("Insufficient balance", 400)

        new_balance = await run_sync(lambda: _apply_withdraw(account, amount))
        return json_response(
            {
                "withdrawn": str(amount),
                "new_balance": str(new_balance),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestTransferView(View):
    """POST /test/transfer - Transfer USDt to another user."""

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
        except ValueError:
            return error_response("Invalid JSON", 400)

        to_telegram_user_id = data.get("to_telegram_user_id")
        if not to_telegram_user_id or not isinstance(to_telegram_user_id, int):
            return error_response("to_telegram_user_id is required", 400)

        amount_value = data.get("amount")
        if amount_value is None:
            amount_value = data.get("amount_usdt")

        try:
            amount = validate_positive_decimal(amount_value, "amount")
        except ValueError as exc:
            return error_response(str(exc), 400)

        if to_telegram_user_id == identity.telegram_user_id:
            return error_response("Cannot transfer to self", 400)

        from_account = await get_account_for_identity(identity)
        if from_account is None:
            return error_response("Account not found", 404)

        if from_account.cash_balance < amount:
            return error_response("Insufficient balance", 400)

        new_balance = await run_sync(
            lambda: _apply_transfer(from_account, to_telegram_user_id, amount)
        )
        if new_balance is None:
            return error_response("Recipient not found", 404)

        return json_response(
            {
                "transferred": str(amount),
                "to_telegram_user_id": to_telegram_user_id,
                "new_balance": str(new_balance),
            }
        )
