from __future__ import annotations

import asyncio
import json
import ssl
import time
from decimal import Decimal
from uuid import uuid4

from pytoniq_core import Address, Cell

from ..constants import (
    ONCHAIN_ASSET_DECIMALS,
    ONCHAIN_OMNISTON_BUILD_TIMEOUT_SECONDS,
    ONCHAIN_OMNISTON_MAX_PRICE_SLIPPAGE_BPS,
    ONCHAIN_OMNISTON_QUOTE_TIMEOUT_SECONDS,
    ONCHAIN_MASTER_ADDRESSES,
    ONCHAIN_OMNISTON_SSL_VERIFY,
    ONCHAIN_OMNISTON_REFERRER_FEE_BPS,
    ONCHAIN_OMNISTON_WS_URL,
    ONCHAIN_TON_BLOCKCHAIN_CODE,
)
from .contracts import SwapBuild, SwapMessage
from .exceptions import OnchainConfigurationError, OnchainStateError

try:
    import certifi
except ModuleNotFoundError:
    certifi = None

try:
    import websockets
except ModuleNotFoundError:
    websockets = None


class OmnistonSwapGateway:
    """Real Omniston RPC transport for swap quoting and transfer-building."""

    _last_quote_frame_excerpt: str = ""
    _settlement_methods: tuple[int, int] = (0, 1)

    @classmethod
    async def swap_exact_input(
        cls,
        wallet_address: str,
        offer_asset_id: str,
        receive_asset_id: str,
        offer_amount: Decimal,
    ) -> SwapBuild:
        if websockets is None:
            raise OnchainConfigurationError("websockets dependency is required for Omniston RPC")
        if offer_amount <= 0:
            raise OnchainStateError("offer_amount must be positive")

        request_id = f"quote-{uuid4().hex}"
        try:
            async with websockets.connect(
                ONCHAIN_OMNISTON_WS_URL,
                ping_interval=20,
                ping_timeout=20,
                ssl=cls._ssl_context(),
            ) as socket:
                await socket.send(
                    json.dumps(
                        cls._quote_request(
                            request_id,
                            wallet_address,
                            offer_asset_id,
                            receive_asset_id,
                            offer_amount,
                        )
                    )
                )
                quote = await cls._wait_for_quote(socket, request_id)
                build_id = f"build-{uuid4().hex}"
                await socket.send(json.dumps(cls._build_transfer_request(build_id, wallet_address, quote)))
                transfer = await cls._wait_for_result(socket, build_id)
        except ssl.SSLCertVerificationError as exc:
            raise OnchainConfigurationError(
                "Omniston TLS verification failed. Install CA bundle or set ONCHAIN_OMNISTON_SSL_VERIFY=false."
            ) from exc
        except ssl.SSLError as exc:
            raise OnchainConfigurationError("Omniston TLS handshake failed") from exc
        except asyncio.TimeoutError as exc:
            raise OnchainStateError("Timed out waiting for Omniston response") from exc

        messages = tuple(cls._parse_messages(transfer))
        if not messages:
            raise OnchainStateError("Omniston returned no transfer messages")

        offer_units = cls._extract_amount_units(quote, "bid")
        receive_units = cls._extract_amount_units(quote, "ask")
        receive_amount = cls._from_units(receive_asset_id, receive_units)
        if receive_amount <= 0:
            raise OnchainStateError("Omniston quote returned zero receive amount")
        execution_price = offer_amount / receive_amount
        return SwapBuild(
            external_order_id=str(quote.get("quote_id") or quote.get("id") or uuid4().hex),
            offer_asset_id=offer_asset_id,
            offer_amount=cls._from_units(offer_asset_id, offer_units),
            receive_asset_id=receive_asset_id,
            receive_amount=receive_amount,
            execution_price=execution_price.quantize(Decimal("0.000001")),
            messages=messages,
            execution_details={
                "provider": "omniston-rpc",
                "offer_asset_id": offer_asset_id,
                "receive_asset_id": receive_asset_id,
                "quote_id": str(quote.get("quote_id") or quote.get("id") or ""),
            },
        )

    @classmethod
    def _quote_request(
        cls,
        request_id: str,
        wallet_address: str,
        offer_asset_id: str,
        receive_asset_id: str,
        offer_amount: Decimal,
    ) -> dict[str, object]:
        params: dict[str, object] = {
            "bid_asset_address": cls._asset_address(offer_asset_id),
            "ask_asset_address": cls._asset_address(receive_asset_id),
            "amount": {
                "bid_units": str(cls._to_units(offer_asset_id, offer_amount)),
            },
            "referrer_fee_bps": ONCHAIN_OMNISTON_REFERRER_FEE_BPS,
            "settlement_methods": list(cls._settlement_methods),
            "settlement_params": {
                "max_price_slippage_bps": ONCHAIN_OMNISTON_MAX_PRICE_SLIPPAGE_BPS,
                "gasless_settlement": 1,
                "max_outgoing_messages": 4,
                "flexible_referrer_fee": False,
            },
        }
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "v1beta7.quote",
            "params": params,
        }

    @classmethod
    def _build_transfer_request(cls, request_id: str, wallet_address: str, quote: dict[str, object]) -> dict[str, object]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "v1beta7.transaction.build_transfer",
            "params": {
                "source_address": cls._wallet_address(wallet_address),
                "destination_address": cls._wallet_address(wallet_address),
                "gas_excess_address": cls._wallet_address(wallet_address),
                "refund_address": cls._wallet_address(wallet_address),
                "quote": quote,
                "use_recommended_slippage": True,
            },
        }

    @classmethod
    async def _wait_for_quote(cls, socket, request_id: str) -> dict[str, object]:
        deadline = time.time() + ONCHAIN_OMNISTON_QUOTE_TIMEOUT_SECONDS
        while time.time() < deadline:
            try:
                raw_message = await asyncio.wait_for(socket.recv(), timeout=max(0.1, deadline - time.time()))
            except asyncio.TimeoutError:
                continue
            cls._last_quote_frame_excerpt = raw_message[:500]
            message = json.loads(raw_message)
            if not isinstance(message, dict):
                continue
            no_quote_error = cls._extract_no_quote(message)
            if no_quote_error is not None:
                raise OnchainStateError(no_quote_error)
            event_error = cls._extract_event_error(message)
            if event_error is not None:
                raise OnchainStateError(cls._format_error(event_error))
            quote = cls._extract_quote(message.get("result")) or cls._extract_quote(message)
            if quote is not None:
                return quote
        if cls._last_quote_frame_excerpt:
            raise OnchainStateError(
                f"Timed out waiting for Omniston quote. Last frame: {cls._last_quote_frame_excerpt}"
            )
        raise OnchainStateError("Timed out waiting for Omniston quote")

    @classmethod
    async def _wait_for_result(cls, socket, request_id: str) -> dict[str, object]:
        deadline = time.time() + ONCHAIN_OMNISTON_BUILD_TIMEOUT_SECONDS
        while time.time() < deadline:
            raw_message = await asyncio.wait_for(socket.recv(), timeout=max(0.1, deadline - time.time()))
            message = json.loads(raw_message)
            if not isinstance(message, dict):
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise OnchainStateError(str(message["error"]))
            result = message.get("result")
            transfer = cls._extract_transfer(result) or cls._extract_transfer(message)
            if transfer is None:
                continue
            return transfer
        raise OnchainStateError("Timed out waiting for Omniston transfer build")

    @classmethod
    def _parse_messages(cls, transfer: dict[str, object]) -> list[SwapMessage]:
        ton_section = transfer.get("ton")
        ton_messages = ton_section.get("messages") if isinstance(ton_section, dict) else []
        nested_result = transfer.get("result")
        nested_messages = nested_result.get("messages") if isinstance(nested_result, dict) else []
        raw_messages = ton_messages or transfer.get("messages") or nested_messages or []
        parsed: list[SwapMessage] = []
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            payload = item.get("payload")
            payload_hex: str | None = None
            if isinstance(payload, str):
                payload_hex = cls._normalize_boc(payload)
            state_init_hex: str | None = None
            state_init = item.get("state_init")
            if isinstance(state_init, str):
                state_init_hex = cls._normalize_boc(state_init)
            parsed.append(
                SwapMessage(
                    target_address=str(item["target_address"]),
                    send_amount=int(item["send_amount"]),
                    payload_boc=payload_hex,
                state_init_boc=state_init_hex,
                )
            )
        return parsed

    @classmethod
    def _extract_transfer(cls, data: object) -> dict[str, object] | None:
        if not isinstance(data, dict):
            return None
        if "ton" in data and isinstance(data["ton"], dict):
            return data
        if "transaction" in data and isinstance(data["transaction"], dict):
            transaction = data["transaction"]
            if "ton" in transaction and isinstance(transaction["ton"], dict):
                return transaction
        for value in data.values():
            if isinstance(value, dict):
                found = cls._extract_transfer(value)
                if found is not None:
                    return found
        return None

    @classmethod
    def _extract_quote(cls, data: object) -> dict[str, object] | None:
        if not isinstance(data, dict):
            return None
        if "bid_units" in data and "ask_units" in data:
            return data
        quote = data.get("quote")
        if isinstance(quote, dict):
            return quote
        for value in data.values():
            if isinstance(value, dict):
                found = cls._extract_quote(value)
                if found is not None:
                    return found
        return None

    @classmethod
    def _extract_event_error(cls, data: object) -> object | None:
        if not isinstance(data, dict):
            return None
        direct_error = data.get("error")
        if direct_error:
            return direct_error
        result = data.get("result")
        if isinstance(result, dict):
            result_error = result.get("error")
            if result_error:
                return result_error
            event_type = str(result.get("type", "")).lower()
            if "rejected" in event_type:
                return result_error or result
        params = data.get("params")
        if isinstance(params, dict):
            return cls._extract_event_error(params)
        return None

    @classmethod
    def _format_error(cls, error: object) -> str:
        if isinstance(error, dict):
            message = error.get("message") or error.get("reason")
            if isinstance(message, str) and message.strip():
                return message.strip()
            try:
                serialized = json.dumps(error)
                if serialized.strip():
                    return serialized
            except Exception:
                return str(error)
        text = str(error)
        return text if text.strip() else repr(error)

    @classmethod
    def _extract_no_quote(cls, data: object) -> str | None:
        if not isinstance(data, dict):
            return None
        params = data.get("params")
        if isinstance(params, dict):
            result = params.get("result")
            if isinstance(result, dict):
                event = result.get("event")
                if isinstance(event, dict) and "no_quote" in event:
                    no_quote = event.get("no_quote")
                    if isinstance(no_quote, dict):
                        reason = no_quote.get("reason") or no_quote.get("message")
                        if isinstance(reason, str) and reason.strip():
                            return f"Omniston returned no quote: {reason.strip()}"
                    return "Omniston returned no quote for this pair right now"
        for value in data.values():
            if isinstance(value, dict):
                found = cls._extract_no_quote(value)
                if found is not None:
                    return found
        return None

    @classmethod
    def _asset_address(cls, asset_id: str) -> dict[str, object]:
        normalized_address = Address(ONCHAIN_MASTER_ADDRESSES[asset_id]).to_str(
            is_user_friendly=True,
            is_url_safe=True,
            is_bounceable=True,
        )
        return {
            "blockchain": ONCHAIN_TON_BLOCKCHAIN_CODE,
            "address": normalized_address,
        }

    @classmethod
    def _wallet_address(cls, wallet_address: str) -> dict[str, object]:
        raw_address = Address(wallet_address).to_str(
            is_user_friendly=False,
        )
        return {
            "blockchain": ONCHAIN_TON_BLOCKCHAIN_CODE,
            "address": raw_address,
        }

    @classmethod
    def _to_units(cls, asset_id: str, amount: Decimal) -> int:
        precision = ONCHAIN_ASSET_DECIMALS[asset_id]
        return int((amount * (Decimal(10) ** precision)).quantize(Decimal("1")))

    @classmethod
    def _from_units(cls, asset_id: str, amount_units: int) -> Decimal:
        precision = ONCHAIN_ASSET_DECIMALS[asset_id]
        return (Decimal(amount_units) / (Decimal(10) ** precision)).quantize(Decimal("0.000001"))

    @staticmethod
    def _looks_like_hex(value: str) -> bool:
        return bool(value) and all(char in "0123456789abcdefABCDEF" for char in value)

    @classmethod
    def _normalize_boc(cls, value: str) -> str:
        if cls._looks_like_hex(value):
            return Cell.one_from_boc(bytes.fromhex(value)).to_boc().hex()
        return Cell.one_from_boc(value).to_boc().hex()

    @classmethod
    def _extract_amount_units(cls, quote: dict[str, object], side: str) -> int:
        candidate_keys = (
            f"{side}_units",
            f"{side}Units",
        )
        for key in candidate_keys:
            raw_value = quote.get(key)
            if raw_value is None:
                continue
            try:
                return int(str(raw_value))
            except (TypeError, ValueError) as exc:
                raise OnchainStateError(f"Invalid Omniston quote field {key}: {raw_value!r}") from exc
        raise OnchainStateError(f"Omniston quote is missing {side} amount units")

    @classmethod
    def _ssl_context(cls) -> ssl.SSLContext | None:
        if not ONCHAIN_OMNISTON_WS_URL.startswith("wss://"):
            return None
        if not ONCHAIN_OMNISTON_SSL_VERIFY:
            insecure_context = ssl.create_default_context()
            insecure_context.check_hostname = False
            insecure_context.verify_mode = ssl.CERT_NONE
            return insecure_context
        if certifi is not None:
            return ssl.create_default_context(cafile=certifi.where())
        return ssl.create_default_context()
