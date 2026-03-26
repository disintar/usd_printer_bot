from decimal import Decimal

from django.test import SimpleTestCase

from onchain.constants import (
    ONCHAIN_OMNISTON_MAX_PRICE_SLIPPAGE_BPS,
    ONCHAIN_OMNISTON_REFERRER_FEE_BPS,
)
from onchain.services.omniston import OmnistonSwapGateway


class OmnistonGatewayTests(SimpleTestCase):
    def test_quote_request_uses_swap_and_escrow_settlement_methods(self) -> None:
        payload = OmnistonSwapGateway._quote_request(
            request_id="quote-1",
            wallet_address="EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c",
            offer_asset_id="AAPLx",
            receive_asset_id="USDt",
            offer_amount=Decimal("1.250000"),
        )

        params = payload["params"]
        self.assertEqual(payload["method"], "v1beta7.quote")
        self.assertEqual(params["settlement_methods"], [0, 1])
        self.assertEqual(params["referrer_fee_bps"], ONCHAIN_OMNISTON_REFERRER_FEE_BPS)
        self.assertEqual(
            params["settlement_params"],
            {
                "max_price_slippage_bps": ONCHAIN_OMNISTON_MAX_PRICE_SLIPPAGE_BPS,
                "gasless_settlement": 1,
                "max_outgoing_messages": 4,
                "flexible_referrer_fee": False,
            },
        )
        self.assertEqual(params["amount"]["bid_units"], "1250000")
