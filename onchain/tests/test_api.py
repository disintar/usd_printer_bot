import json
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch

from django.test import Client, TestCase

from onchain.models import OnchainWallet
from onchain.services.contracts import CreatedWallet, SwapBuild, SwapExecution, SwapMessage, WithdrawalExecution
from wallet.models import TelegramIdentity


class OnchainApiTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def _post(self, path: str, payload: dict[str, Any], token: str | None = None) -> Any:
        headers: dict[str, str] = {}
        if token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def _get(self, path: str, token: str | None = None) -> Any:
        headers: dict[str, str] = {}
        if token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.get(path, **headers)

    def _auth(self, telegram_user_id: int = 9001) -> str:
        response = self._post(
            "/auth/telegram",
            {"telegram_user_id": telegram_user_id, "username": f"user{telegram_user_id}"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]["token"]

    def _identity(self, telegram_user_id: int) -> TelegramIdentity:
        return TelegramIdentity.objects.get(telegram_user_id=telegram_user_id)

    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.create_wallet_v5",
        new_callable=AsyncMock,
    )
    def test_create_wallet_and_get_address(self, mock_create_wallet: AsyncMock) -> None:
        token = self._auth()
        mock_create_wallet.return_value = CreatedWallet(
            address="EQTESTONCHAINADDRESS",
            seed_phrase="one two three",
            version="v5r1",
        )

        create_response = self._post("/onchain/wallet/create", {}, token)
        self.assertEqual(create_response.status_code, 200)
        payload = create_response.json()["data"]
        self.assertEqual(payload["address"], "EQTESTONCHAINADDRESS")
        self.assertEqual(payload["version"], "v5r1")

        address_response = self._get("/onchain/address", token)
        self.assertEqual(address_response.status_code, 200)
        self.assertEqual(address_response.json()["data"]["address"], "EQTESTONCHAINADDRESS")
        self.assertTrue(OnchainWallet.objects.filter(address="EQTESTONCHAINADDRESS").exists())

    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.deploy_wallet",
        new_callable=AsyncMock,
    )
    def test_deploy_wallet_endpoint(self, mock_deploy_wallet: AsyncMock) -> None:
        telegram_user_id = 9010
        token = self._auth(telegram_user_id)
        OnchainWallet.objects.create(
            identity=self._identity(telegram_user_id),
            address="EQDEPLOY",
            seed_phrase="seed words",
            version="v5r1",
        )
        mock_deploy_wallet.return_value = "deploy-tx-hash"

        response = self._post("/onchain/deploy", {}, token)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["address"], "EQDEPLOY")
        self.assertEqual(data["tx_hash"], "deploy-tx-hash")

    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.ensure_wallet_ready",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.get_asset_balances",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.submit_swap",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.omniston.OmnistonSwapGateway.swap_exact_input",
        new_callable=AsyncMock,
    )
    def test_buy_updates_balance_pnl_and_orders(
        self,
        mock_swap: AsyncMock,
        mock_submit_swap: AsyncMock,
        mock_chain_balances: AsyncMock,
        mock_ensure_wallet_ready: AsyncMock,
    ) -> None:
        telegram_user_id = 9002
        token = self._auth(telegram_user_id)
        wallet = OnchainWallet.objects.create(
            identity=self._identity(telegram_user_id),
            address="EQBUYTEST",
            seed_phrase="seed words",
            version="v5r1",
            usdt_balance=Decimal("1000"),
        )
        self.assertEqual(wallet.usdt_balance, Decimal("1000"))

        mock_chain_balances.side_effect = [
            {"USDt": Decimal("1000.000000"), "AAPLx": Decimal("0.000000")},
            {"USDt": Decimal("900.000000"), "AAPLx": Decimal("0.500000")},
            {"USDt": Decimal("900.000000"), "AAPLx": Decimal("0.500000")},
        ]
        mock_swap.return_value = SwapBuild(
            external_order_id="order-1",
            offer_asset_id="USDt",
            offer_amount=Decimal("100.000000"),
            receive_asset_id="AAPLx",
            receive_amount=Decimal("0.500000"),
            execution_price=Decimal("200.000000"),
            messages=(SwapMessage(target_address="EQ1", send_amount=1, payload_boc=None, state_init_boc=None),),
            execution_details={"provider": "omniston"},
        )
        mock_submit_swap.return_value = SwapExecution(
            external_order_id="order-1",
            tx_hash="",
            offer_asset_id="USDt",
            offer_amount=Decimal("100.000000"),
            receive_asset_id="AAPLx",
            receive_amount=Decimal("0.500000"),
            execution_price=Decimal("200.000000"),
            execution_details={"provider": "omniston"},
        )

        buy_response = self._post("/onchain/buy", {"asset_id": "AAPLx", "amount_usdt": "100"}, token)
        self.assertEqual(buy_response.status_code, 200)
        order_payload = buy_response.json()["data"]
        self.assertEqual(order_payload["offer_amount"], "100.000000")
        self.assertEqual(order_payload["receive_amount"], "0.500000")
        mock_ensure_wallet_ready.assert_awaited_once()

        balance_response = self._get("/onchain/balance", token)
        self.assertEqual(balance_response.status_code, 200)
        balance = balance_response.json()["data"]
        self.assertEqual(balance["cash_usdt"], "900.000000")
        self.assertEqual(balance["equity_usdt"], "996.400000")
        self.assertEqual(balance["total_balance_usdt"], "996.400000")
        self.assertEqual(balance["pnl_absolute"], "-3.60")
        self.assertEqual(balance["pnl_percent"], "-3.60")
        assets = {asset["asset_id"]: asset for asset in balance["assets"]}
        self.assertEqual(assets["USDt"]["balance"], "900.000000")
        self.assertEqual(assets["USDt"]["pnl_absolute"], "0.00")
        self.assertEqual(assets["AAPLx"]["balance"], "0.500000")
        self.assertEqual(assets["AAPLx"]["net_worth"], "96.400000")
        self.assertEqual(assets["AAPLx"]["pnl_absolute"], "-3.60")
        self.assertEqual(assets["AAPLx"]["pnl_percent"], "-3.60")
        self.assertIn("TSLAx", assets)
        self.assertEqual(assets["TSLAx"]["balance"], "0.000000")
        self.assertEqual(assets["TSLAx"]["net_worth"], "0.000000")

        orders_response = self._get("/onchain/orders", token)
        self.assertEqual(orders_response.status_code, 200)
        orders = orders_response.json()["data"]["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["side"], "buy")
        self.assertEqual(orders[0]["tx_hash"], "")
        self.assertEqual(orders[0]["realized_pnl"], "0.00")
        self.assertEqual(orders[0]["realized_pnl_percent"], "0.00")

    @patch(
        "onchain.services.orders.ONCHAIN_SEND_TX_TIMEOUT_SECONDS",
        1,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.ensure_wallet_ready",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.get_asset_balances",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.submit_swap",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.omniston.OmnistonSwapGateway.swap_exact_input",
        new_callable=AsyncMock,
    )
    def test_buy_does_not_persist_when_swap_does_not_settle(
        self,
        mock_swap: AsyncMock,
        mock_submit_swap: AsyncMock,
        mock_chain_balances: AsyncMock,
        mock_ensure_wallet_ready: AsyncMock,
    ) -> None:
        telegram_user_id = 9011
        token = self._auth(telegram_user_id)
        wallet = OnchainWallet.objects.create(
            identity=self._identity(telegram_user_id),
            address="EQBUYFAIL",
            seed_phrase="seed words",
            version="v5r1",
            usdt_balance=Decimal("1000"),
        )

        mock_chain_balances.side_effect = [
            {"USDt": Decimal("1000.000000")},
            {"USDt": Decimal("1000.000000"), "AAPLx": Decimal("0.000000")},
        ]
        mock_swap.return_value = SwapBuild(
            external_order_id="order-buy-fail",
            offer_asset_id="USDt",
            offer_amount=Decimal("100.000000"),
            receive_asset_id="AAPLx",
            receive_amount=Decimal("0.500000"),
            execution_price=Decimal("200.000000"),
            messages=(SwapMessage(target_address="EQ1", send_amount=1, payload_boc=None, state_init_boc=None),),
            execution_details={"provider": "omniston"},
        )
        mock_submit_swap.return_value = SwapExecution(
            external_order_id="order-buy-fail",
            tx_hash="",
            offer_asset_id="USDt",
            offer_amount=Decimal("100.000000"),
            receive_asset_id="AAPLx",
            receive_amount=Decimal("0.500000"),
            execution_price=Decimal("200.000000"),
            execution_details={"provider": "omniston"},
        )

        response = self._post("/onchain/buy", {"asset_id": "AAPLx", "amount_usdt": "100"}, token)
        self.assertEqual(response.status_code, 400)
        wallet.refresh_from_db()
        self.assertEqual(wallet.orders.count(), 0)
        self.assertEqual(wallet.positions.count(), 0)

    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.ensure_wallet_ready",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.get_asset_balances",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.withdraw_usdt",
        new_callable=AsyncMock,
    )
    def test_withdraw_creates_order_and_reduces_cash(
        self,
        mock_withdraw: AsyncMock,
        mock_chain_balances: AsyncMock,
        mock_ensure_wallet_ready: AsyncMock,
    ) -> None:
        telegram_user_id = 9003
        token = self._auth(telegram_user_id)
        OnchainWallet.objects.create(
            identity=self._identity(telegram_user_id),
            address="EQWITHDRAW",
            seed_phrase="seed words",
            version="v5r1",
            usdt_balance=Decimal("0"),
        )
        mock_chain_balances.side_effect = [
            {"USDt": Decimal("250.000000")},
            {"USDt": Decimal("225.000000")},
        ]
        mock_withdraw.return_value = WithdrawalExecution(
            tx_hash="",
            destination_address="EQDEST",
            amount=Decimal("25.000000"),
        )

        withdraw_response = self._post(
            "/onchain/withdraw",
            {"amount_usdt": "25", "destination_address": "EQDEST"},
            token,
        )
        self.assertEqual(withdraw_response.status_code, 200)
        payload = withdraw_response.json()["data"]
        self.assertEqual(payload["notional"], "25.000000")
        self.assertEqual(payload["tx_hash"], "")
        mock_ensure_wallet_ready.assert_awaited_once()

        balance = self._get("/onchain/balance", token).json()["data"]
        self.assertEqual(balance["cash_usdt"], "225.000000")

    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.ensure_wallet_ready",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.get_asset_balances",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.submit_swap",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.omniston.OmnistonSwapGateway.swap_exact_input",
        new_callable=AsyncMock,
    )
    def test_sell_uses_quantity_and_updates_realized_pnl(
        self,
        mock_swap: AsyncMock,
        mock_submit_swap: AsyncMock,
        mock_chain_balances: AsyncMock,
        mock_ensure_wallet_ready: AsyncMock,
    ) -> None:
        telegram_user_id = 9004
        token = self._auth(telegram_user_id)
        wallet = OnchainWallet.objects.create(
            identity=self._identity(telegram_user_id),
            address="EQSELL",
            seed_phrase="seed words",
            version="v5r1",
            usdt_balance=Decimal("0"),
            cumulative_invested_usdt=Decimal("100"),
        )
        wallet.positions.create(
            asset_id="AAPLx",
            quantity=Decimal("0.500000"),
            average_entry_price=Decimal("200.000000"),
        )
        mock_chain_balances.side_effect = [
            {"AAPLx": Decimal("0.500000"), "USDt": Decimal("0.000000")},
            {"AAPLx": Decimal("0.250000"), "USDt": Decimal("55.000000")},
        ]
        mock_swap.return_value = SwapBuild(
            external_order_id="order-sell",
            offer_asset_id="AAPLx",
            offer_amount=Decimal("0.250000"),
            receive_asset_id="USDt",
            receive_amount=Decimal("55.000000"),
            execution_price=Decimal("220.000000"),
            messages=(SwapMessage(target_address="EQ1", send_amount=1, payload_boc=None, state_init_boc=None),),
            execution_details={"provider": "omniston"},
        )
        mock_submit_swap.return_value = SwapExecution(
            external_order_id="order-sell",
            tx_hash="",
            offer_asset_id="AAPLx",
            offer_amount=Decimal("0.250000"),
            receive_asset_id="USDt",
            receive_amount=Decimal("55.000000"),
            execution_price=Decimal("220.000000"),
            execution_details={"provider": "omniston"},
        )

        sell_response = self._post("/onchain/sell", {"asset_id": "AAPLx", "quantity": "0.25"}, token)
        self.assertEqual(sell_response.status_code, 200)
        mock_ensure_wallet_ready.assert_awaited_once()
        order_payload = sell_response.json()["data"]
        self.assertEqual(order_payload["realized_pnl"], "5.00")
        self.assertEqual(order_payload["realized_pnl_percent"], "10.00")
        balance = self._get("/onchain/balance", token).json()["data"]
        self.assertEqual(balance["cash_usdt"], "55.000000")
        self.assertEqual(balance["pnl_absolute"], "3.20")
        self.assertEqual(balance["pnl_percent"], "3.20")
        assets = {asset["asset_id"]: asset for asset in balance["assets"]}
        self.assertEqual(assets["USDt"]["balance"], "55.000000")
        orders = self._get("/onchain/orders", token).json()["data"]["orders"]
        self.assertEqual(orders[0]["realized_pnl"], "5.00")
        self.assertEqual(orders[0]["realized_pnl_percent"], "10.00")

    @patch(
        "onchain.services.orders.ONCHAIN_SEND_TX_TIMEOUT_SECONDS",
        1,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.ensure_wallet_ready",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.get_asset_balances",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.submit_swap",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.omniston.OmnistonSwapGateway.swap_exact_input",
        new_callable=AsyncMock,
    )
    def test_sell_does_not_persist_when_swap_does_not_settle(
        self,
        mock_swap: AsyncMock,
        mock_submit_swap: AsyncMock,
        mock_chain_balances: AsyncMock,
        mock_ensure_wallet_ready: AsyncMock,
    ) -> None:
        telegram_user_id = 9012
        token = self._auth(telegram_user_id)
        wallet = OnchainWallet.objects.create(
            identity=self._identity(telegram_user_id),
            address="EQSELLFAIL",
            seed_phrase="seed words",
            version="v5r1",
            usdt_balance=Decimal("0"),
            cumulative_invested_usdt=Decimal("100"),
        )
        wallet.positions.create(
            asset_id="AAPLx",
            quantity=Decimal("0.500000"),
            average_entry_price=Decimal("200.000000"),
        )

        mock_chain_balances.side_effect = [
            {"AAPLx": Decimal("0.500000")},
            {"USDt": Decimal("0.000000")},
            {"AAPLx": Decimal("0.500000"), "USDt": Decimal("0.000000")},
        ]
        mock_swap.return_value = SwapBuild(
            external_order_id="order-sell-fail",
            offer_asset_id="AAPLx",
            offer_amount=Decimal("0.250000"),
            receive_asset_id="USDt",
            receive_amount=Decimal("55.000000"),
            execution_price=Decimal("220.000000"),
            messages=(SwapMessage(target_address="EQ1", send_amount=1, payload_boc=None, state_init_boc=None),),
            execution_details={"provider": "omniston"},
        )
        mock_submit_swap.return_value = SwapExecution(
            external_order_id="order-sell-fail",
            tx_hash="",
            offer_asset_id="AAPLx",
            offer_amount=Decimal("0.250000"),
            receive_asset_id="USDt",
            receive_amount=Decimal("55.000000"),
            execution_price=Decimal("220.000000"),
            execution_details={"provider": "omniston"},
        )

        response = self._post("/onchain/sell", {"asset_id": "AAPLx", "quantity": "0.25"}, token)
        self.assertEqual(response.status_code, 400)
        wallet.refresh_from_db()
        position = wallet.positions.get(asset_id="AAPLx")
        self.assertEqual(position.quantity, Decimal("0.500000"))
        self.assertEqual(wallet.orders.count(), 0)

    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.ensure_wallet_ready",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.get_asset_balances",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.submit_swap",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.omniston.OmnistonSwapGateway.swap_exact_input",
        new_callable=AsyncMock,
    )
    def test_sell_accepts_amount_alias(
        self,
        mock_swap: AsyncMock,
        mock_submit_swap: AsyncMock,
        mock_chain_balances: AsyncMock,
        mock_ensure_wallet_ready: AsyncMock,
    ) -> None:
        telegram_user_id = 9005
        token = self._auth(telegram_user_id)
        wallet = OnchainWallet.objects.create(
            identity=self._identity(telegram_user_id),
            address="EQSELLALIAS",
            seed_phrase="seed words",
            version="v5r1",
            usdt_balance=Decimal("0"),
            cumulative_invested_usdt=Decimal("100"),
        )
        wallet.positions.create(
            asset_id="NVDAx",
            quantity=Decimal("0.000558"),
            average_entry_price=Decimal("178.028674"),
        )
        mock_chain_balances.side_effect = [
            {"NVDAx": Decimal("0.000558"), "USDt": Decimal("0.999800")},
            {"NVDAx": Decimal("0.000000"), "USDt": Decimal("1.099140")},
        ]
        mock_swap.return_value = SwapBuild(
            external_order_id="order-sell-alias",
            offer_asset_id="NVDAx",
            offer_amount=Decimal("0.000558"),
            receive_asset_id="USDt",
            receive_amount=Decimal("0.099340"),
            execution_price=Decimal("178.028674"),
            messages=(SwapMessage(target_address="EQ1", send_amount=1, payload_boc=None, state_init_boc=None),),
            execution_details={"provider": "omniston"},
        )
        mock_submit_swap.return_value = SwapExecution(
            external_order_id="order-sell-alias",
            tx_hash="",
            offer_asset_id="NVDAx",
            offer_amount=Decimal("0.000558"),
            receive_asset_id="USDt",
            receive_amount=Decimal("0.099340"),
            execution_price=Decimal("178.028674"),
            execution_details={"provider": "omniston"},
        )

        sell_response = self._post("/onchain/sell", {"asset_id": "NVDAx", "amount": "0.000558"}, token)
        self.assertEqual(sell_response.status_code, 200)
        self.assertEqual(sell_response.json()["data"]["offer_amount"], "0.000558")
        mock_ensure_wallet_ready.assert_awaited_once()

    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.ensure_wallet_ready",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.get_asset_balances",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.submit_swap",
        new_callable=AsyncMock,
    )
    @patch(
        "onchain.services.omniston.OmnistonSwapGateway.swap_exact_input",
        new_callable=AsyncMock,
    )
    def test_sell_accepts_amount_usdt_alias(
        self,
        mock_swap: AsyncMock,
        mock_submit_swap: AsyncMock,
        mock_chain_balances: AsyncMock,
        mock_ensure_wallet_ready: AsyncMock,
    ) -> None:
        telegram_user_id = 9006
        token = self._auth(telegram_user_id)
        wallet = OnchainWallet.objects.create(
            identity=self._identity(telegram_user_id),
            address="EQSELLUSDTALIAS",
            seed_phrase="seed words",
            version="v5r1",
            usdt_balance=Decimal("0"),
            cumulative_invested_usdt=Decimal("100"),
        )
        wallet.positions.create(
            asset_id="NVDAx",
            quantity=Decimal("0.000558"),
            average_entry_price=Decimal("178.028674"),
        )
        mock_chain_balances.side_effect = [
            {"NVDAx": Decimal("0.000558"), "USDt": Decimal("0.999800")},
            {"NVDAx": Decimal("0.000000"), "USDt": Decimal("1.099140")},
        ]
        mock_swap.return_value = SwapBuild(
            external_order_id="order-sell-usdt-alias",
            offer_asset_id="NVDAx",
            offer_amount=Decimal("0.000558"),
            receive_asset_id="USDt",
            receive_amount=Decimal("0.099340"),
            execution_price=Decimal("178.028674"),
            messages=(SwapMessage(target_address="EQ1", send_amount=1, payload_boc=None, state_init_boc=None),),
            execution_details={"provider": "omniston"},
        )
        mock_submit_swap.return_value = SwapExecution(
            external_order_id="order-sell-usdt-alias",
            tx_hash="",
            offer_asset_id="NVDAx",
            offer_amount=Decimal("0.000558"),
            receive_asset_id="USDt",
            receive_amount=Decimal("0.099340"),
            execution_price=Decimal("178.028674"),
            execution_details={"provider": "omniston"},
        )

        sell_response = self._post("/onchain/sell", {"asset_id": "NVDAx", "amount_usdt": "0.000558"}, token)
        self.assertEqual(sell_response.status_code, 200)
        self.assertEqual(sell_response.json()["data"]["offer_amount"], "0.000558")
        mock_ensure_wallet_ready.assert_awaited_once()

    @patch(
        "onchain.services.balances.PricesService.get_all_prices",
        return_value={"USDt": Decimal("1.00"), "NVDAx": Decimal("188.54")},
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.get_asset_balances",
        new_callable=AsyncMock,
    )
    def test_balance_uses_position_cost_basis_for_asset_pnl(
        self,
        mock_chain_balances: AsyncMock,
        mock_get_all_prices,
    ) -> None:
        telegram_user_id = 9007
        token = self._auth(telegram_user_id)
        wallet = OnchainWallet.objects.create(
            identity=self._identity(telegram_user_id),
            address="EQBALANCEFIX",
            seed_phrase="seed words",
            version="v5r1",
            usdt_balance=Decimal("0"),
            cumulative_invested_usdt=Decimal("0.099340"),
        )
        wallet.positions.create(
            asset_id="NVDAx",
            quantity=Decimal("0.055800"),
            average_entry_price=Decimal("1.780287"),
        )
        mock_chain_balances.return_value = {
            "USDt": Decimal("0"),
            "NVDAx": Decimal("0.000558"),
        }

        balance_response = self._get("/onchain/balance", token)
        self.assertEqual(balance_response.status_code, 200)
        assets = {asset["asset_id"]: asset for asset in balance_response.json()["data"]["assets"]}
        self.assertEqual(assets["NVDAx"]["pnl_absolute"], "0.01")
        self.assertEqual(assets["NVDAx"]["pnl_percent"], "5.87")

    @patch(
        "onchain.services.balances.PricesService.get_all_prices",
        return_value={"USDt": Decimal("1.00"), "AAPLx": Decimal("188.54")},
    )
    @patch(
        "onchain.services.pytoniq_wallet.PytoniqWalletGateway.get_asset_balances",
        new_callable=AsyncMock,
    )
    def test_balance_uses_chain_quantity_when_chain_balance_lags(
        self,
        mock_chain_balances: AsyncMock,
        mock_get_all_prices,
    ) -> None:
        telegram_user_id = 9008
        token = self._auth(telegram_user_id)
        wallet = OnchainWallet.objects.create(
            identity=self._identity(telegram_user_id),
            address="EQBALANCELAG",
            seed_phrase="seed words",
            version="v5r1",
            usdt_balance=Decimal("0"),
            cumulative_invested_usdt=Decimal("100.000000"),
        )
        wallet.positions.create(
            asset_id="AAPLx",
            quantity=Decimal("0.500000"),
            average_entry_price=Decimal("200.000000"),
        )
        mock_chain_balances.return_value = {
            "USDt": Decimal("900.000000"),
            "AAPLx": Decimal("0.000000"),
        }

        balance_response = self._get("/onchain/balance", token)
        self.assertEqual(balance_response.status_code, 200)
        assets = {asset["asset_id"]: asset for asset in balance_response.json()["data"]["assets"]}
        self.assertEqual(assets["AAPLx"]["balance"], "0.000000")
        self.assertEqual(assets["AAPLx"]["net_worth"], "0.000000")
