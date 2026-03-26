from __future__ import annotations

import asyncio
import json
import socket
import struct
from contextlib import asynccontextmanager
from decimal import Decimal
from importlib import import_module
from typing import ClassVar
from weakref import WeakKeyDictionary

from pytoniq_core import Address, Cell, begin_cell
from pytoniq_core.tlb.account import StateInit
from pytoniq_core.tlb.custom.wallet import WalletMessage

from ..constants import (
    ONCHAIN_ASSET_DECIMALS,
    ONCHAIN_JETTON_TRANSFER_TON_ATTACH,
    ONCHAIN_LITESERVER_CONFIG,
    ONCHAIN_MASTER_ADDRESSES,
    ONCHAIN_NETWORK_GLOBAL_ID,
    ONCHAIN_SEND_TX_TIMEOUT_SECONDS,
    ONCHAIN_UI_SCALE_FACTORS,
)
from .contracts import CreatedWallet, SwapExecution, SwapMessage, WithdrawalExecution
from .exceptions import OnchainConfigurationError, OnchainStateError


class PytoniqWalletGateway:
    """Real TON/LiteServer gateway backed by pytoniq."""

    _provider_lock: ClassVar[asyncio.Lock | None] = None
    _providers_by_loop: ClassVar[WeakKeyDictionary] = WeakKeyDictionary()
    _wallet_locks_by_loop: ClassVar[WeakKeyDictionary] = WeakKeyDictionary()
    _jetton_wallet_cache: ClassVar[dict[tuple[str, str], str]] = {}
    _wallet_ready_cache: ClassVar[dict[str, float]] = {}
    _wallet_ready_ttl_seconds: ClassVar[float] = 10.0
    _retriable_liteserver_error_codes: ClassVar[set[int]] = {228, 651}

    @classmethod
    def _load_pytoniq(cls):
        try:
            pytoniq_module = import_module("pytoniq")
            wallets_module = import_module("pytoniq.contract.wallets")
        except ModuleNotFoundError as exc:
            raise OnchainConfigurationError("pytoniq is not installed in the runtime") from exc
        return pytoniq_module, wallets_module

    @classmethod
    def _parse_liteserver_config(cls) -> dict:
        if not ONCHAIN_LITESERVER_CONFIG.strip():
            raise OnchainConfigurationError("ONCHAIN_LITESERVER env is required")
        try:
            raw_config = json.loads(ONCHAIN_LITESERVER_CONFIG)
        except json.JSONDecodeError as exc:
            raise OnchainConfigurationError("ONCHAIN_LITESERVER must be valid JSON") from exc

        if "liteservers" not in raw_config:
            raw_config = {"liteservers": [raw_config]}

        if "validator" not in raw_config:
            raw_config["validator"] = {
                "init_block": {
                    "workchain": -1,
                    "seqno": 0,
                    "root_hash": "",
                    "file_hash": "",
                }
            }
        return raw_config

    @classmethod
    def _create_single_provider(cls):
        pytoniq_module, _ = cls._load_pytoniq()
        config = cls._parse_liteserver_config()
        if config["validator"]["init_block"]["root_hash"]:
            return pytoniq_module.LiteBalancer.from_config(config=config, trust_level=1, timeout=15)

        lite_server = config["liteservers"][0]
        host = socket.inet_ntoa(struct.pack(">i", lite_server["ip"]))
        client = pytoniq_module.LiteClient(
            host=host,
            port=lite_server["port"],
            server_pub_key=lite_server["id"]["key"],
            trust_level=1,
            timeout=15,
        )
        return pytoniq_module.LiteBalancer([client], timeout=15)

    @classmethod
    @asynccontextmanager
    async def _provider(cls):
        provider = await cls._get_shared_provider()
        yield provider

    @classmethod
    async def _get_shared_provider(cls, force_refresh: bool = False):
        if cls._provider_lock is None:
            cls._provider_lock = asyncio.Lock()
        current_loop = asyncio.get_running_loop()
        async with cls._provider_lock:
            provider = cls._providers_by_loop.get(current_loop)
            if force_refresh and provider is not None:
                await cls._close_provider(provider)
                cls._providers_by_loop.pop(current_loop, None)
                provider = None
            if provider is not None and getattr(provider, "inited", False):
                return provider
            if provider is not None and not getattr(provider, "inited", False):
                cls._providers_by_loop.pop(current_loop, None)
            provider = cls._create_single_provider()
            await provider.__aenter__()
            cls._providers_by_loop[current_loop] = provider
            return provider

    @classmethod
    async def _close_provider(cls, provider) -> None:
        exit_method = getattr(provider, "__aexit__", None)
        if exit_method is None:
            return
        try:
            await exit_method(None, None, None)
        except Exception:
            return

    @classmethod
    async def _reset_provider(cls) -> None:
        current_loop = asyncio.get_running_loop()
        if cls._provider_lock is None:
            cls._provider_lock = asyncio.Lock()
        async with cls._provider_lock:
            provider = cls._providers_by_loop.pop(current_loop, None)
            if provider is not None:
                await cls._close_provider(provider)
        cls._jetton_wallet_cache.clear()
        cls._wallet_ready_cache.clear()

    @classmethod
    def _should_retry_liteserver_error(cls, exc: Exception) -> bool:
        error_code = getattr(exc, "code", None)
        if isinstance(error_code, int) and error_code in cls._retriable_liteserver_error_codes:
            return True
        message = str(exc).lower()
        return "block is not in db" in message or "out of sync" in message or "ratelimit" in message

    @classmethod
    async def _run_with_provider_retry(cls, operation):
        attempts = 2
        last_error: Exception | None = None
        for attempt_index in range(attempts):
            provider = await cls._get_shared_provider(force_refresh=attempt_index > 0)
            try:
                return await operation(provider)
            except Exception as exc:
                last_error = exc
                if not cls._should_retry_liteserver_error(exc) or attempt_index == attempts - 1:
                    raise
                await cls._reset_provider()
        if last_error is not None:
            raise last_error
        raise OnchainStateError("LiteServer request failed")

    @classmethod
    def _get_wallet_lock(cls, wallet_address: str) -> asyncio.Lock:
        current_loop = asyncio.get_running_loop()
        loop_locks = cls._wallet_locks_by_loop.get(current_loop)
        if loop_locks is None:
            loop_locks = {}
            cls._wallet_locks_by_loop[current_loop] = loop_locks
        wallet_lock = loop_locks.get(wallet_address)
        if wallet_lock is None:
            wallet_lock = asyncio.Lock()
            loop_locks[wallet_address] = wallet_lock
        return wallet_lock

    @classmethod
    async def create_wallet_v5(cls) -> CreatedWallet:
        _, wallets_module = cls._load_pytoniq()
        wallet_class = getattr(wallets_module, "WalletV5R1", None)
        if wallet_class is None:
            raise OnchainConfigurationError("installed pytoniq build does not expose WalletV5R1")

        async with cls._provider() as provider:
            mnemonics, wallet = await wallet_class.create(
                provider=provider,
                network_global_id=ONCHAIN_NETWORK_GLOBAL_ID,
            )
        address = wallet.address.to_str(
            is_user_friendly=True,
            is_url_safe=True,
            is_bounceable=True,
        )
        return CreatedWallet(address=address, seed_phrase=" ".join(mnemonics), version="v5r1")

    @classmethod
    async def get_asset_balances(
        cls,
        wallet_address: str,
        asset_ids: tuple[str, ...] | None = None,
    ) -> dict[str, Decimal]:
        target_asset_ids = asset_ids if asset_ids is not None else tuple(ONCHAIN_MASTER_ADDRESSES.keys())

        async def _load_balances(provider) -> dict[str, Decimal]:
            balances: dict[str, Decimal] = {}
            for asset_id in target_asset_ids:
                master_address = ONCHAIN_MASTER_ADDRESSES[asset_id]
                balances[asset_id] = await cls._get_jetton_balance(provider, wallet_address, master_address, asset_id)
            return balances

        return await cls._run_with_provider_retry(_load_balances)

    @classmethod
    async def get_asset_balance(cls, wallet_address: str, asset_id: str) -> Decimal:
        balances = await cls.get_asset_balances(wallet_address, asset_ids=(asset_id,))
        return balances.get(asset_id, Decimal("0"))

    @classmethod
    async def deploy_wallet(cls, seed_phrase: str, wallet_address: str) -> str:
        return await cls._run_with_provider_retry(
            lambda provider: cls._deploy_wallet_with_provider(provider, seed_phrase, wallet_address)
        )

    @classmethod
    async def ensure_wallet_ready(cls, seed_phrase: str, wallet_address: str) -> str:
        async def _ensure(provider):
            _, wallets_module = cls._load_pytoniq()
            wallet = await wallets_module.WalletV5R1.from_mnemonic(
                provider=provider,
                mnemonics=seed_phrase,
                network_global_id=ONCHAIN_NETWORK_GLOBAL_ID,
            )
            expected_address = wallet.address.to_str(
                is_user_friendly=True,
                is_url_safe=True,
                is_bounceable=True,
            )
            if expected_address != wallet_address:
                raise OnchainStateError("Seed phrase does not match wallet address stored in database")
            return await cls._ensure_wallet_is_active(wallet, expected_address)

        return await cls._run_with_provider_retry(_ensure)

    @classmethod
    async def withdraw_usdt(
        cls,
        seed_phrase: str,
        wallet_address: str,
        destination_address: str,
        amount: Decimal,
    ) -> WithdrawalExecution:
        async def _withdraw(provider) -> WithdrawalExecution:
            sender_jetton_wallet = await cls._resolve_jetton_wallet_address(
                provider=provider,
                owner_address=wallet_address,
                master_address=ONCHAIN_MASTER_ADDRESSES["USDt"],
            )
            body = cls._build_jetton_transfer_body(
                amount=cls._to_units("USDt", amount),
                destination_address=destination_address,
                response_address=wallet_address,
            )
            message = SwapMessage(
                target_address=sender_jetton_wallet,
                send_amount=ONCHAIN_JETTON_TRANSFER_TON_ATTACH,
                payload_boc=body.to_boc().hex(),
                state_init_boc=None,
            )
            tx_hash = await cls._send_messages_with_provider(
                provider=provider,
                seed_phrase=seed_phrase,
                wallet_address=wallet_address,
                messages=(message,),
            )
            return WithdrawalExecution(
                tx_hash=tx_hash,
                destination_address=destination_address,
                amount=amount.quantize(Decimal("0.000001")),
            )

        return await cls._run_with_provider_retry(_withdraw)

    @classmethod
    async def submit_swap(
        cls,
        seed_phrase: str,
        wallet_address: str,
        messages: tuple[SwapMessage, ...],
        execution,
    ) -> SwapExecution:
        tx_hash = await cls.send_messages(
            seed_phrase=seed_phrase,
            wallet_address=wallet_address,
            messages=messages,
        )
        return SwapExecution(
            external_order_id=execution.external_order_id,
            tx_hash=tx_hash,
            offer_asset_id=execution.offer_asset_id,
            offer_amount=execution.offer_amount,
            receive_asset_id=execution.receive_asset_id,
            receive_amount=execution.receive_amount,
            execution_price=execution.execution_price,
            execution_details=execution.execution_details,
        )

    @classmethod
    async def send_messages(
        cls,
        seed_phrase: str,
        wallet_address: str,
        messages: tuple[SwapMessage, ...],
    ) -> str:
        if not messages:
            raise OnchainStateError("messages are required")

        return await cls._run_with_provider_retry(
            lambda provider: cls._send_messages_with_provider(
                provider=provider,
                seed_phrase=seed_phrase,
                wallet_address=wallet_address,
                messages=messages,
            )
        )

    @classmethod
    async def _send_messages_with_provider(
        cls,
        provider,
        seed_phrase: str,
        wallet_address: str,
        messages: tuple[SwapMessage, ...],
    ) -> str:
        wallet_lock = cls._get_wallet_lock(wallet_address)
        async with wallet_lock:
            _, wallets_module = cls._load_pytoniq()
            wallet = await wallets_module.WalletV5R1.from_mnemonic(
                provider=provider,
                mnemonics=seed_phrase,
                network_global_id=ONCHAIN_NETWORK_GLOBAL_ID,
            )
            expected_address = wallet.address.to_str(
                is_user_friendly=True,
                is_url_safe=True,
                is_bounceable=True,
            )
            if expected_address != wallet_address:
                raise OnchainStateError(
                    "Seed phrase does not match wallet address stored in database"
                )
            await cls._ensure_wallet_is_active(wallet, expected_address)
            wallet_messages = [cls._to_wallet_message(message) for message in messages]
            await wallet.raw_transfer(wallet_messages)
            return ""

    @classmethod
    async def _deploy_wallet_with_provider(cls, provider, seed_phrase: str, wallet_address: str) -> str:
        _, wallets_module = cls._load_pytoniq()
        wallet = await wallets_module.WalletV5R1.from_mnemonic(
            provider=provider,
            mnemonics=seed_phrase,
            network_global_id=ONCHAIN_NETWORK_GLOBAL_ID,
        )
        expected_address = wallet.address.to_str(
            is_user_friendly=True,
            is_url_safe=True,
            is_bounceable=True,
        )
        if expected_address != wallet_address:
            raise OnchainStateError("Seed phrase does not match wallet address stored in database")
        return await cls._ensure_wallet_is_active(wallet, expected_address)

    @classmethod
    async def _ensure_wallet_is_active(cls, wallet, wallet_address: str) -> str:
        now = asyncio.get_running_loop().time()
        cached_until = cls._wallet_ready_cache.get(wallet_address, 0.0)
        if cached_until > now:
            return ""
        account = await wallet.provider.get_account_state(wallet.address)
        if account.is_active():
            cls._wallet_ready_cache[wallet_address] = now + cls._wallet_ready_ttl_seconds
            return ""
        balance_ton = Decimal(account.balance) / Decimal(10**9)
        if account.balance <= 0:
            raise OnchainStateError(
                f"Wallet is not deployed on-chain yet. Current state={account.state.type_}, "
                f"ton_balance={balance_ton:.9f}. Deploy/fund the wallet first, then retry."
            )
        await wallet.deploy_via_external()
        tx_hash = await cls._wait_for_wallet_activation_and_tx_hash(wallet.provider, wallet_address)
        active_account = await wallet.provider.get_account_state(wallet.address)
        if not active_account.is_active():
            raise OnchainStateError(
                f"Wallet deploy was sent but state is still {active_account.state.type_}. "
                f"ton_balance={Decimal(active_account.balance) / Decimal(10**9):.9f}"
            )
        cls._wallet_ready_cache[wallet_address] = asyncio.get_running_loop().time() + cls._wallet_ready_ttl_seconds
        return tx_hash

    @classmethod
    async def _wait_for_wallet_activation_and_tx_hash(cls, provider, wallet_address: str) -> str:
        deadline = asyncio.get_running_loop().time() + ONCHAIN_SEND_TX_TIMEOUT_SECONDS
        while asyncio.get_running_loop().time() < deadline:
            account = await provider.get_account_state(wallet_address)
            if account.is_active():
                transactions = await provider.get_transactions(wallet_address, count=1)
                if transactions:
                    return transactions[0].cell.hash.hex()
                return ""
            await asyncio.sleep(2)
        return ""

    @classmethod
    async def _get_jetton_balance(cls, provider, owner_address: str, master_address: str, asset_id: str) -> Decimal:
        jetton_wallet_address = await cls._resolve_jetton_wallet_address(provider, owner_address, master_address)
        account_state = await provider.get_account_state(jetton_wallet_address)
        if not account_state.is_active():
            return Decimal("0")
        wallet_data = await provider.run_get_method(jetton_wallet_address, "get_wallet_data", [])
        raw_balance = int(wallet_data[0])
        return cls._from_units(asset_id, raw_balance)

    @classmethod
    async def _resolve_jetton_wallet_address(cls, provider, owner_address: str, master_address: str) -> str:
        cache_key = (owner_address, master_address)
        cached_address = cls._jetton_wallet_cache.get(cache_key)
        if cached_address is not None:
            return cached_address
        owner_slice = begin_cell().store_address(Address(owner_address)).end_cell().begin_parse()
        result = await provider.run_get_method(master_address, "get_wallet_address", [owner_slice])
        item = result[0]
        if hasattr(item, "load_address"):
            address = item.load_address().to_str(is_user_friendly=True, is_url_safe=True, is_bounceable=True)
            cls._jetton_wallet_cache[cache_key] = address
            return address
        if hasattr(item, "begin_parse"):
            address = item.begin_parse().load_address().to_str(
                is_user_friendly=True,
                is_url_safe=True,
                is_bounceable=True,
            )
            cls._jetton_wallet_cache[cache_key] = address
            return address
        raise OnchainStateError("Unable to parse jetton wallet address")

    @classmethod
    def _build_jetton_transfer_body(
        cls,
        amount: int,
        destination_address: str,
        response_address: str,
    ) -> Cell:
        return (
            begin_cell()
            .store_uint(0x0F8A7EA5, 32)
            .store_uint(0, 64)
            .store_coins(amount)
            .store_address(Address(destination_address))
            .store_address(Address(response_address))
            .store_bit(0)
            .store_coins(1)
            .store_bit(0)
            .end_cell()
        )

    @classmethod
    def _to_wallet_message(cls, message: SwapMessage) -> WalletMessage:
        _, wallets_module = cls._load_pytoniq()
        body = cls._load_boc_cell(message.payload_boc) if message.payload_boc else Cell.empty()
        state_init = None
        if message.state_init_boc:
            state_init = StateInit.deserialize(cls._load_boc_cell(message.state_init_boc).begin_parse())
        destination = Address(message.target_address)
        wallet_message = wallets_module.WalletV5R1.create_wallet_internal_message(
            destination=destination,
            value=message.send_amount,
            body=body,
            state_init=state_init,
        )
        return wallet_message

    @classmethod
    def _to_units(cls, asset_id: str, amount: Decimal) -> int:
        precision = ONCHAIN_ASSET_DECIMALS[asset_id]
        scale_factor = ONCHAIN_UI_SCALE_FACTORS[asset_id]
        scaled_amount = amount / scale_factor
        return int((scaled_amount * (Decimal(10) ** precision)).quantize(Decimal("1")))

    @classmethod
    def _from_units(cls, asset_id: str, amount_units: int) -> Decimal:
        precision = ONCHAIN_ASSET_DECIMALS[asset_id]
        scale_factor = ONCHAIN_UI_SCALE_FACTORS[asset_id]
        ui_amount = (Decimal(amount_units) / (Decimal(10) ** precision)) * scale_factor
        return ui_amount.quantize(Decimal("0.000001"))

    @staticmethod
    def _load_boc_cell(serialized_boc: str) -> Cell:
        if all(char in "0123456789abcdefABCDEF" for char in serialized_boc):
            return Cell.one_from_boc(bytes.fromhex(serialized_boc))
        return Cell.one_from_boc(serialized_boc)
