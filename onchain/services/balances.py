from __future__ import annotations

from decimal import Decimal

from asgiref.sync import sync_to_async

from ..models import OnchainWallet
from .contracts import BalanceAssetSnapshot, BalanceSnapshot
from .pytoniq_wallet import PytoniqWalletGateway
from wallet.constants import TRADEABLE_ASSET_IDS
from wallet.services.prices import PricesService


class OnchainBalanceService:
    _balance_quant = Decimal("0.000001")
    _pnl_quant = Decimal("0.01")
    _zero = Decimal("0")

    @classmethod
    async def get_balance(cls, wallet: OnchainWallet) -> BalanceSnapshot:
        positions = await sync_to_async(
            lambda: list(wallet.positions.filter(quantity__gt=0)),
            thread_sensitive=True,
        )()
        positions_by_asset = {position.asset_id: position for position in positions}
        current_prices = await sync_to_async(PricesService.get_all_prices, thread_sensitive=True)()
        asset_ids = tuple(["USDt", *TRADEABLE_ASSET_IDS])
        chain_balances = await PytoniqWalletGateway.get_asset_balances(wallet.address, asset_ids=asset_ids)
        open_cost_basis = Decimal("0")
        open_market_value = Decimal("0")

        for position in positions:
            current_price = current_prices.get(position.asset_id, Decimal("0"))
            chain_quantity = chain_balances.get(position.asset_id, Decimal("0"))
            open_cost_basis += position.quantity * position.average_entry_price
            open_market_value += chain_quantity * current_price

        unrealized_pnl = open_market_value - open_cost_basis
        pnl_absolute = wallet.realized_pnl_usdt + unrealized_pnl
        invested = wallet.cumulative_invested_usdt
        if invested > 0:
            pnl_percent = (pnl_absolute / invested) * Decimal("100")
        else:
            pnl_percent = Decimal("0")

        cash_balance = chain_balances.get("USDt", Decimal("0"))
        total_balance = cash_balance + open_market_value
        assets: list[BalanceAssetSnapshot] = []

        if cash_balance > 0:
            cash_allocation = (cash_balance / total_balance * Decimal("100")) if total_balance > 0 else cls._zero
            assets.append(
                BalanceAssetSnapshot(
                    asset_id="USDt",
                    balance=cash_balance.quantize(cls._balance_quant),
                    current_price=Decimal("1.000000"),
                    net_worth=cash_balance.quantize(cls._balance_quant),
                    pnl_percent=cls._zero.quantize(cls._pnl_quant),
                    pnl_absolute=cls._zero.quantize(cls._pnl_quant),
                    allocation_percent=cash_allocation.quantize(cls._pnl_quant),
                )
            )

        for asset_id in TRADEABLE_ASSET_IDS:
            chain_quantity = chain_balances.get(asset_id, cls._zero)
            if asset_id == "USDt":
                continue
            position = positions_by_asset.get(asset_id)
            current_price = current_prices.get(asset_id, cls._zero)
            net_worth = chain_quantity * current_price
            pnl_absolute_asset = cls._zero
            pnl_percent_asset = cls._zero
            if position is not None and position.average_entry_price > 0:
                entry_value = position.quantity * position.average_entry_price
                pnl_absolute_asset = net_worth - entry_value
                if entry_value > 0:
                    pnl_percent_asset = (pnl_absolute_asset / entry_value) * Decimal("100")
            allocation_percent = (net_worth / total_balance * Decimal("100")) if total_balance > 0 else cls._zero
            assets.append(
                BalanceAssetSnapshot(
                    asset_id=asset_id,
                    balance=chain_quantity.quantize(cls._balance_quant),
                    current_price=current_price.quantize(cls._balance_quant),
                    net_worth=net_worth.quantize(cls._balance_quant),
                    pnl_percent=pnl_percent_asset.quantize(cls._pnl_quant),
                    pnl_absolute=pnl_absolute_asset.quantize(cls._pnl_quant),
                    allocation_percent=allocation_percent.quantize(cls._pnl_quant),
                )
            )

        return BalanceSnapshot(
            cash_usdt=cash_balance.quantize(cls._balance_quant),
            equity_usdt=total_balance.quantize(cls._balance_quant),
            total_balance_usdt=total_balance.quantize(cls._balance_quant),
            pnl_percent=pnl_percent.quantize(cls._pnl_quant),
            pnl_absolute=pnl_absolute.quantize(cls._pnl_quant),
            assets=assets,
        )
