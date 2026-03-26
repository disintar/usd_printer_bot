from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SwapMessage:
    target_address: str
    send_amount: int
    payload_boc: str | None
    state_init_boc: str | None


@dataclass(frozen=True)
class CreatedWallet:
    address: str
    seed_phrase: str
    version: str


@dataclass(frozen=True)
class WithdrawalExecution:
    tx_hash: str
    destination_address: str
    amount: Decimal


@dataclass(frozen=True)
class SwapExecution:
    external_order_id: str
    tx_hash: str
    offer_asset_id: str
    offer_amount: Decimal
    receive_asset_id: str
    receive_amount: Decimal
    execution_price: Decimal
    execution_details: dict[str, str]


@dataclass(frozen=True)
class SwapBuild:
    external_order_id: str
    offer_asset_id: str
    offer_amount: Decimal
    receive_asset_id: str
    receive_amount: Decimal
    execution_price: Decimal
    messages: tuple[SwapMessage, ...]
    execution_details: dict[str, str]


@dataclass(frozen=True)
class BalanceAssetSnapshot:
    asset_id: str
    balance: Decimal
    current_price: Decimal
    net_worth: Decimal
    pnl_percent: Decimal
    pnl_absolute: Decimal
    allocation_percent: Decimal


@dataclass(frozen=True)
class BalanceSnapshot:
    cash_usdt: Decimal
    equity_usdt: Decimal
    total_balance_usdt: Decimal
    pnl_percent: Decimal
    pnl_absolute: Decimal
    assets: list[BalanceAssetSnapshot]
