from __future__ import annotations

import asyncio
from decimal import Decimal

from asgiref.sync import sync_to_async
from django.db import transaction

from ..constants import (
    ONCHAIN_SEND_TX_TIMEOUT_SECONDS,
    ONCHAIN_USDT_ASSET_ID,
    SUPPORTED_ONCHAIN_ASSET_IDS,
)
from ..models import OnchainOrder, OnchainPosition, OnchainWallet
from .contracts import CreatedWallet, SwapBuild, SwapExecution, WithdrawalExecution
from .exceptions import OnchainStateError
from .omniston import OmnistonSwapGateway
from .pytoniq_wallet import PytoniqWalletGateway


class OnchainWalletService:
    @classmethod
    async def create_wallet(cls, identity) -> OnchainWallet:
        existing_wallet = await sync_to_async(
            lambda: OnchainWallet.objects.filter(identity=identity).first(),
            thread_sensitive=True,
        )()
        if existing_wallet is not None:
            return existing_wallet

        created = await PytoniqWalletGateway.create_wallet_v5()
        return await sync_to_async(
            lambda: cls._persist_created_wallet(identity, created),
            thread_sensitive=True,
        )()

    @staticmethod
    def _persist_created_wallet(identity, created: CreatedWallet) -> OnchainWallet:
        return OnchainWallet.objects.create(
            identity=identity,
            address=created.address,
            seed_phrase=created.seed_phrase,
            version=created.version,
        )

    @staticmethod
    def require_wallet(identity) -> OnchainWallet:
        wallet = OnchainWallet.objects.filter(identity=identity).first()
        if wallet is None:
            raise OnchainStateError("Onchain wallet not found")
        return wallet

    @classmethod
    async def deploy_wallet(cls, wallet: OnchainWallet) -> str:
        return await PytoniqWalletGateway.deploy_wallet(
            seed_phrase=wallet.seed_phrase,
            wallet_address=wallet.address,
        )


class OnchainOrderService:
    @classmethod
    async def withdraw_usdt(
        cls,
        wallet: OnchainWallet,
        amount: Decimal,
        destination_address: str,
    ) -> OnchainOrder:
        await PytoniqWalletGateway.ensure_wallet_ready(
            seed_phrase=wallet.seed_phrase,
            wallet_address=wallet.address,
        )
        usdt_balance = await PytoniqWalletGateway.get_asset_balance(wallet.address, ONCHAIN_USDT_ASSET_ID)
        if usdt_balance < amount:
            raise OnchainStateError("Insufficient USDT balance")
        execution = await PytoniqWalletGateway.withdraw_usdt(
            seed_phrase=wallet.seed_phrase,
            wallet_address=wallet.address,
            destination_address=destination_address,
            amount=amount,
        )
        return await sync_to_async(
            lambda: cls._apply_withdrawal(wallet, execution),
            thread_sensitive=True,
        )()

    @classmethod
    async def swap_usdt_to_asset(
        cls,
        wallet: OnchainWallet,
        asset_id: str,
        amount_usdt: Decimal,
    ) -> OnchainOrder:
        cls._validate_stock_asset(asset_id)
        await PytoniqWalletGateway.ensure_wallet_ready(
            seed_phrase=wallet.seed_phrase,
            wallet_address=wallet.address,
        )
        usdt_balance = await PytoniqWalletGateway.get_asset_balance(wallet.address, ONCHAIN_USDT_ASSET_ID)
        if usdt_balance < amount_usdt:
            raise OnchainStateError("Insufficient USDT balance")
        swap_build = await OmnistonSwapGateway.swap_exact_input(
            wallet_address=wallet.address,
            offer_asset_id=ONCHAIN_USDT_ASSET_ID,
            receive_asset_id=asset_id,
            offer_amount=amount_usdt,
        )
        execution = await PytoniqWalletGateway.submit_swap(
            wallet.seed_phrase,
            wallet.address,
            swap_build.messages,
            swap_build,
        )
        await cls._await_buy_settlement(
            wallet=wallet,
            asset_id=asset_id,
            previous_usdt_balance=usdt_balance,
        )
        return await sync_to_async(
            lambda: cls._apply_buy(wallet, asset_id, execution),
            thread_sensitive=True,
        )()

    @classmethod
    async def swap_asset_to_usdt(
        cls,
        wallet: OnchainWallet,
        asset_id: str,
        quantity: Decimal,
    ) -> OnchainOrder:
        cls._validate_stock_asset(asset_id)
        await PytoniqWalletGateway.ensure_wallet_ready(
            seed_phrase=wallet.seed_phrase,
            wallet_address=wallet.address,
        )
        asset_balance = await PytoniqWalletGateway.get_asset_balance(wallet.address, asset_id)
        usdt_balance = await PytoniqWalletGateway.get_asset_balance(wallet.address, ONCHAIN_USDT_ASSET_ID)
        if asset_balance < quantity:
            raise OnchainStateError("Insufficient position balance")
        swap_build = await OmnistonSwapGateway.swap_exact_input(
            wallet_address=wallet.address,
            offer_asset_id=asset_id,
            receive_asset_id=ONCHAIN_USDT_ASSET_ID,
            offer_amount=quantity,
        )
        execution = await PytoniqWalletGateway.submit_swap(
            wallet.seed_phrase,
            wallet.address,
            swap_build.messages,
            swap_build,
        )
        await cls._await_sell_settlement(
            wallet=wallet,
            asset_id=asset_id,
            previous_asset_balance=asset_balance,
            previous_usdt_balance=usdt_balance,
        )
        return await sync_to_async(
            lambda: cls._apply_sell(wallet, asset_id, execution),
            thread_sensitive=True,
        )()

    @staticmethod
    def _validate_stock_asset(asset_id: str) -> None:
        if asset_id not in SUPPORTED_ONCHAIN_ASSET_IDS:
            raise OnchainStateError("Unsupported asset_id")

    @classmethod
    async def _await_buy_settlement(
        cls,
        wallet: OnchainWallet,
        asset_id: str,
        previous_usdt_balance: Decimal,
    ) -> None:
        deadline = asyncio.get_running_loop().time() + ONCHAIN_SEND_TX_TIMEOUT_SECONDS
        while asyncio.get_running_loop().time() < deadline:
            balances = await PytoniqWalletGateway.get_asset_balances(
                wallet.address,
                asset_ids=(ONCHAIN_USDT_ASSET_ID, asset_id),
            )
            current_asset_balance = balances.get(asset_id, Decimal("0"))
            current_usdt_balance = balances.get(ONCHAIN_USDT_ASSET_ID, Decimal("0"))
            if current_asset_balance > Decimal("0") or current_usdt_balance < previous_usdt_balance:
                return
            await asyncio.sleep(2)
        raise OnchainStateError("Swap was sent but did not settle on-chain")

    @classmethod
    async def _await_sell_settlement(
        cls,
        wallet: OnchainWallet,
        asset_id: str,
        previous_asset_balance: Decimal,
        previous_usdt_balance: Decimal,
    ) -> None:
        deadline = asyncio.get_running_loop().time() + ONCHAIN_SEND_TX_TIMEOUT_SECONDS
        while asyncio.get_running_loop().time() < deadline:
            balances = await PytoniqWalletGateway.get_asset_balances(
                wallet.address,
                asset_ids=(ONCHAIN_USDT_ASSET_ID, asset_id),
            )
            current_asset_balance = balances.get(asset_id, Decimal("0"))
            current_usdt_balance = balances.get(ONCHAIN_USDT_ASSET_ID, Decimal("0"))
            if current_asset_balance < previous_asset_balance or current_usdt_balance > previous_usdt_balance:
                return
            await asyncio.sleep(2)
        raise OnchainStateError("Swap was sent but did not settle on-chain")

    @staticmethod
    @transaction.atomic
    def _apply_withdrawal(wallet: OnchainWallet, execution: WithdrawalExecution) -> OnchainOrder:
        wallet = OnchainWallet.objects.select_for_update().get(pk=wallet.pk)
        wallet.usdt_balance = wallet.usdt_balance - execution.amount
        wallet.save(update_fields=["usdt_balance", "updated_at"])
        return OnchainOrder.objects.create(
            wallet=wallet,
            side=OnchainOrder.SIDE_WITHDRAW,
            asset_id=ONCHAIN_USDT_ASSET_ID,
            quantity=execution.amount,
            price=Decimal("1"),
            notional=execution.amount,
            offer_asset_id=ONCHAIN_USDT_ASSET_ID,
            offer_amount=execution.amount,
            receive_asset_id=ONCHAIN_USDT_ASSET_ID,
            receive_amount=execution.amount,
            destination_address=execution.destination_address,
            tx_hash=execution.tx_hash,
            execution_details={
                "provider": "pytoniq",
                "tx_hash": execution.tx_hash,
                "realized_pnl": "0.00",
                "realized_pnl_percent": "0.00",
            },
        )

    @staticmethod
    @transaction.atomic
    def _apply_buy(wallet: OnchainWallet, asset_id: str, execution: SwapExecution) -> OnchainOrder:
        wallet = OnchainWallet.objects.select_for_update().get(pk=wallet.pk)
        position, _ = OnchainPosition.objects.select_for_update().get_or_create(
            wallet=wallet,
            asset_id=asset_id,
            defaults={"quantity": Decimal("0"), "average_entry_price": Decimal("0")},
        )

        total_cost = (position.quantity * position.average_entry_price) + execution.offer_amount
        new_quantity = position.quantity + execution.receive_amount
        position.quantity = new_quantity
        position.average_entry_price = total_cost / new_quantity
        position.save(update_fields=["quantity", "average_entry_price", "updated_at"])

        wallet.usdt_balance -= execution.offer_amount
        wallet.cumulative_invested_usdt += execution.offer_amount
        wallet.save(update_fields=["usdt_balance", "cumulative_invested_usdt", "updated_at"])

        return OnchainOrder.objects.create(
            wallet=wallet,
            side=OnchainOrder.SIDE_BUY,
            asset_id=asset_id,
            quantity=execution.receive_amount,
            price=execution.execution_price,
            notional=execution.offer_amount,
            offer_asset_id=execution.offer_asset_id,
            offer_amount=execution.offer_amount,
            receive_asset_id=execution.receive_asset_id,
            receive_amount=execution.receive_amount,
            external_order_id=execution.external_order_id,
            tx_hash=execution.tx_hash,
            execution_details={
                **execution.execution_details,
                "realized_pnl": "0.00",
                "realized_pnl_percent": "0.00",
            },
        )

    @staticmethod
    @transaction.atomic
    def _apply_sell(wallet: OnchainWallet, asset_id: str, execution: SwapExecution) -> OnchainOrder:
        wallet = OnchainWallet.objects.select_for_update().get(pk=wallet.pk)
        position = OnchainPosition.objects.select_for_update().filter(
            wallet=wallet,
            asset_id=asset_id,
        ).first()
        if position is None or position.quantity < execution.offer_amount:
            raise OnchainStateError("Insufficient position balance")

        cost_basis = position.average_entry_price * execution.offer_amount
        realized = execution.receive_amount - cost_basis
        realized_pnl_percent = (
            (realized / cost_basis) * Decimal("100")
            if cost_basis > 0
            else Decimal("0")
        )
        position.quantity -= execution.offer_amount
        if position.quantity == 0:
            position.average_entry_price = Decimal("0")
        position.save(update_fields=["quantity", "average_entry_price", "updated_at"])

        wallet.usdt_balance += execution.receive_amount
        wallet.realized_pnl_usdt += realized
        wallet.save(update_fields=["usdt_balance", "realized_pnl_usdt", "updated_at"])

        return OnchainOrder.objects.create(
            wallet=wallet,
            side=OnchainOrder.SIDE_SELL,
            asset_id=asset_id,
            quantity=execution.offer_amount,
            price=execution.execution_price,
            notional=execution.receive_amount,
            offer_asset_id=execution.offer_asset_id,
            offer_amount=execution.offer_amount,
            receive_asset_id=execution.receive_asset_id,
            receive_amount=execution.receive_amount,
            external_order_id=execution.external_order_id,
            tx_hash=execution.tx_hash,
            execution_details={
                **execution.execution_details,
                "realized_pnl": str(realized.quantize(Decimal("0.01"))),
                "realized_pnl_percent": str(realized_pnl_percent.quantize(Decimal("0.01"))),
            },
        )

    @staticmethod
    def get_orders(wallet: OnchainWallet) -> list[OnchainOrder]:
        return list(wallet.orders.order_by("-created_at"))

    @staticmethod
    def get_order(wallet: OnchainWallet, order_id: int) -> OnchainOrder | None:
        return wallet.orders.filter(id=order_id).first()
