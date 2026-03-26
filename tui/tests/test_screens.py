"""Tests for TUI screens."""
from __future__ import annotations

import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from tui.api import UnauthorizedError
from tui.app import WalletTUI
from tui.modals.order import OrderModal
from tui.screens.login import LoginScreen
from tui.screens.dashboard import MainScreen
from tui.screens.orders import OrdersScreen
from tui.screens.portfolio import PortfolioScreen
from tui.screens.rebalance import RebalanceScreen


class FakeApi:
    """Simple in-memory API for runtime screen tests."""

    class Config:
        token = "fake-session-token"

    def __init__(self) -> None:
        self.config = self.Config()

    def get_balance(self) -> dict:
        return {
            "cash_usdt": "10000.00",
            "equity_usdt": "2500.00",
            "total_balance_usdt": "12500.00",
            "pnl_percent": "25.00",
            "pnl_absolute": "2500.00",
        }

    def get_positions(self) -> list[dict]:
        return [
            {
                "asset_id": "AAPLx",
                "quantity": "2",
                "net_worth": "385.60",
                "pnl_percent": "3.50",
                "mark": "Buy",
            }
        ]

    def get_assets(self) -> list[dict]:
        return [
            {
                "asset_id": "AAPLx",
                "current_price": "192.80",
                "balance": "2.0",
                "net_worth": "385.60",
                "mark": "Buy",
            },
            {
                "asset_id": "TSLAx",
                "current_price": "201.10",
                "balance": "1.0",
                "net_worth": "201.10",
                "mark": "Hold",
            },
        ]

    def get_asset(self, asset_id: str) -> dict:
        return {
            "asset_id": asset_id,
            "balance": "2.0",
            "current_price": "192.80",
            "net_worth": "385.60",
            "pnl_percent": "3.50",
            "pnl_absolute": "13.10",
            "mark": "Buy",
            "agent_marks": {"Buy": "Buy", "Hold": "Hold"},
        }

    def get_portfolio(self) -> dict:
        return {
            "total_balance_usdt": "12500.00",
            "pnl_percent": "25.00",
            "pnl_absolute": "2500.00",
            "assets": [
                {
                    "asset_id": "AAPLx",
                    "quantity": "2",
                    "value_usdt": "385.60",
                    "allocation_percent": "3.08",
                },
                {
                    "asset_id": "USDt",
                    "quantity": "10000",
                    "value_usdt": "10000.00",
                    "allocation_percent": "80.00",
                },
            ],
        }

    def get_risk(self) -> dict:
        return {"risk_score": "35", "risk_level": "low"}

    def get_address(self) -> dict:
        return {"address": "0xabc123"}

    def get_prices(self) -> dict:
        return {
            "USDt": "1.00",
            "AAPLx": "192.80",
            "NVDAx": "821.70",
            "TSLAx": "215.40",
            "COINx": "198.25",
        }

    def get_time(self) -> dict:
        return {
            "server_time_utc": "2026-03-25T00:00:00+00:00",
            "simulated_time_utc": "2026-01-24T00:00:00+00:00",
            "test_time_warp_enabled": True,
            "window_days": 60,
            "hours_per_tick": 1,
        }

    def get_reasoning(self, asset_id: str) -> dict:
        return {
            "asset_id": asset_id,
            "recommendation": "Buy",
            "reasoning": ["Momentum strong", "Risk acceptable"],
        }

    def get_allocation(self) -> dict:
        return {
            "allocation": {"Buy": 20.0, "Cover": 20.0, "Sell": 20.0, "Short": 20.0, "Hold": 20.0}
        }

    def rebalance(self) -> dict:
        return {"actions": [{"action": "BUY", "asset_id": "AAPLx", "reason": "Below target"}]}

    def get_order(self, order_id: int) -> dict:
        return {
            "order_id": order_id,
            "side": "buy",
            "asset_id": "AAPLx",
            "quantity": "1",
            "price": "192.80",
            "notional": "192.80",
            "status": "filled",
        }

    def get_advisors_list(self) -> list[dict[str, object]]:
        return [
            {"id": "warren_buffett", "name": "Warren Buffett", "category": "serious"},
            {"id": "pavel_durov", "name": "Pavel Durov", "category": "serious"},
            {"id": "cathie_wood", "name": "Cathie Wood", "category": "serious"},
            {"id": "gordon_gekko", "name": "Gordon Gekko", "category": "playful"},
        ]

    def get_advisor_preferences(self) -> dict[str, object]:
        return {"selected_advisors": ["warren_buffett", "pavel_durov"], "risk_profile": "medium"}

    def update_advisor_preferences(self, selected_advisors: list[str], risk_profile: str) -> dict[str, object]:
        return {"selected_advisors": selected_advisors, "risk_profile": risk_profile}

    def get_advisor_analysis(self, asset_id: str) -> dict[str, object]:
        return {
            "asset_id": asset_id,
            "recommendation": "buy",
            "summary": "Advisor summary.",
            "advisor_notes": [
                {"advisor_id": "warren_buffett", "name": "Warren Buffett", "thought": "Moat looks strong."},
                {"advisor_id": "pavel_durov", "name": "Pavel Durov", "thought": "Product growth is visible."},
            ],
        }


class ChangingAssetsApi(FakeApi):
    """API stub that changes all asset prices on each call."""

    def __init__(self) -> None:
        super().__init__()
        self._tick = 0

    def get_assets(self) -> list[dict]:
        self._tick += 1
        aapl_price = 190 + self._tick
        tsla_price = 200 + self._tick
        return [
            {
                "asset_id": "AAPLx",
                "current_price": f"{aapl_price:.2f}",
                "balance": "2.0",
                "net_worth": f"{(2 * aapl_price):.2f}",
                "mark": "Buy",
            },
            {
                "asset_id": "TSLAx",
                "current_price": f"{tsla_price:.2f}",
                "balance": "1.0",
                "net_worth": f"{tsla_price:.2f}",
                "mark": "Hold",
            },
        ]


class UnauthorizedApi(FakeApi):
    """API stub that always returns unauthorized for protected calls."""

    def get_balance(self) -> dict:
        raise UnauthorizedError("Authentication required")


class NoTokenApi(FakeApi):
    class Config:
        token = None

    def __init__(self) -> None:
        self.config = self.Config()

    def get_balance(self) -> dict:
        raise AssertionError("get_balance must not be called without token")


class AdvisorTrackingApi(FakeApi):
    def __init__(self) -> None:
        super().__init__()
        self.last_selected_advisors: list[str] | None = None
        self.last_asset_id: str | None = None
        self.analysis_calls: int = 0

    def update_advisor_preferences(self, selected_advisors: list[str], risk_profile: str) -> dict[str, object]:
        self.last_selected_advisors = list(selected_advisors)
        return super().update_advisor_preferences(selected_advisors, risk_profile)

    def get_advisor_analysis(self, asset_id: str) -> dict[str, object]:
        self.analysis_calls += 1
        self.last_asset_id = asset_id
        return super().get_advisor_analysis(asset_id)


class UsdtFirstAssetsApi(AdvisorTrackingApi):
    def get_assets(self) -> list[dict]:
        return [
            {
                "asset_id": "USDt",
                "current_price": "1.00",
                "balance": "10000.0",
                "net_worth": "10000.00",
                "mark": "Hold",
            },
            {
                "asset_id": "AAPLx",
                "current_price": "192.80",
                "balance": "2.0",
                "net_worth": "385.60",
                "mark": "Buy",
            },
        ]


class TestLoginScreen:
    """Tests for LoginScreen."""

    def test_login_screen_composes(self) -> None:
        """Test that LoginScreen can be instantiated."""
        screen = LoginScreen()
        assert screen is not None

    def test_login_screen_has_login_button(self) -> None:
        """Test that LoginScreen has the login button."""
        screen = LoginScreen()
        # Check button IDs that should exist
        assert hasattr(screen, "compose")

    def test_login_screen_default_state(self) -> None:
        """Test LoginScreen default state."""
        screen = LoginScreen()
        assert screen.pending_token is None
        assert screen.polling_active is False


class TestMainScreen:
    """Tests for MainScreen."""

    def test_main_screen_composes(self) -> None:
        """Test that MainScreen can be instantiated."""
        screen = MainScreen()
        assert screen is not None

    def test_main_screen_bindings(self) -> None:
        """Test MainScreen has correct bindings."""
        bindings = MainScreen.BINDINGS
        binding_keys = [b.key for b in bindings]

        assert "q" in binding_keys  # Quit
        assert "r" in binding_keys  # Refresh
        assert "b" in binding_keys  # Buy
        assert "s" in binding_keys  # Sell

    def test_main_screen_refresh_data_mounts_without_errors(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            app.api = FakeApi()

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)

                # Regression guard for "Can't mount widget(s) before Vertical() is mounted"
                main._update_balance()
                await pilot.pause()
                label_texts = [str(widget.render()) for widget in main.query(".balance-label")]
                assert any("Cash" in text for text in label_texts), f"Cash not found in {label_texts}"
                assert any("Total" in text for text in label_texts), f"Total not found in {label_texts}"

        asyncio.run(_run())

    def test_buy_modal_closes_and_refreshes_positions(self) -> None:
        class BuyRefreshApi(FakeApi):
            def __init__(self) -> None:
                super().__init__()
                self._positions: list[dict] = []

            def get_positions(self) -> list[dict]:
                return list(self._positions)

            def buy(self, asset_id: str, quantity: str) -> dict:
                self._positions.append(
                    {
                        "asset_id": asset_id.upper().replace("X", "x").replace("aaplx", "AAPLx"),
                        "quantity": quantity,
                        "net_worth": "192.80",
                        "pnl_percent": "0.00",
                        "mark": "Buy",
                    }
                )
                return {
                    "order_id": 1,
                    "asset_id": "AAPLx",
                    "quantity": quantity,
                    "price": "192.80",
                    "status": "filled",
                }

        async def _run() -> None:
            app = WalletTUI()
            app.api = BuyRefreshApi()

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)
                positions = main.query_one("#positions-table")
                assert getattr(positions, "row_count", 0) == 0

                app.push_screen("order_buy")
                await pilot.pause()
                modal = app.screen
                assert isinstance(modal, OrderModal)

                modal.query_one("#asset_id").value = "AAPLx"
                modal.query_one("#quantity").value = "1"
                modal._place_order()
                await pilot.pause()

                assert isinstance(app.screen, MainScreen)
                main_after = app.get_screen("main")
                updated_positions = main_after.query_one("#positions-table")
                assert getattr(updated_positions, "row_count", 0) >= 1

        asyncio.run(_run())

    def test_buy_and_sell_actions_use_current_table_selection(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            app.api = FakeApi()

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)

                assets_table = main.query_one("#assets-table")
                assets_table.focus()
                assets_table.move_cursor(row=1, column=0, animate=False, scroll=False)
                await pilot.pause()
                main.action_buy()
                await pilot.pause()
                buy_modal = app.screen
                assert isinstance(buy_modal, OrderModal)
                assert buy_modal.query_one("#asset_id").value == "TSLAx"
                assert buy_modal.query_one("#asset_id").disabled is True
                assert buy_modal.query_one("#quantity").has_focus
                app.pop_screen()
                await pilot.pause()

                positions_table = main.query_one("#positions-table")
                positions_table.focus()
                positions_table.move_cursor(row=0, column=0, animate=False, scroll=False)
                await pilot.pause()
                main.action_sell()
                await pilot.pause()
                sell_modal = app.screen
                assert isinstance(sell_modal, OrderModal)
                assert sell_modal.query_one("#asset_id").value == "AAPLx"
                assert sell_modal.query_one("#asset_id").disabled is True
                assert sell_modal.query_one("#quantity").has_focus

        asyncio.run(_run())

    def test_buy_prefers_selected_asset_when_no_table_focus(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            app.api = FakeApi()

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)

                main.selected_asset = "TSLAx"
                main.set_focus(None)
                main.action_buy()
                await pilot.pause()

                modal = app.screen
                assert isinstance(modal, OrderModal)
                assert modal.query_one("#asset_id").value == "TSLAx"
                assert modal.query_one("#asset_id").disabled is True
                assert modal.query_one("#quantity").has_focus

        asyncio.run(_run())

    def test_main_screen_has_no_top_action_buttons(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            app.api = FakeApi()

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)
                assert len(main.query("#btn-buy")) == 0
                assert len(main.query("#btn-sell")) == 0
                assert len(main.query("#btn-deposit")) == 0
                assert len(main.query("#btn-withdraw")) == 0
                assert len(main.query("#btn-transfer")) == 0

        asyncio.run(_run())

    def test_assets_refresh_keeps_cursor_and_updates_all_symbols(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            app.api = ChangingAssetsApi()

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)

                table = main.query_one("#assets-table")
                row_before_aapl = table.get_row_at(0)
                row_before_tsla = table.get_row_at(1)

                table.move_cursor(row=1, column=0, animate=False, scroll=False)
                await pilot.pause()
                main.refresh_data()
                await pilot.pause()

                row_after_aapl = table.get_row_at(0)
                row_after_tsla = table.get_row_at(1)

                assert table.cursor_row == 1
                assert str(row_before_aapl[1]) != str(row_after_aapl[1])
                assert str(row_before_tsla[1]) != str(row_after_tsla[1])

        asyncio.run(_run())

    def test_unauthorized_refresh_redirects_to_login(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            app.api = UnauthorizedApi()

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)
                main.refresh_data()
                await pilot.pause()
                assert isinstance(app.screen, LoginScreen)

        asyncio.run(_run())

    def test_main_screen_skips_refresh_when_token_missing(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            app.api = NoTokenApi()
            async with app.run_test() as pilot:
                app.push_screen("main")
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)
                main.refresh_data()
                await pilot.pause()
                assert isinstance(app.screen, MainScreen)

        asyncio.run(_run())


class TestWalletTUI:
    """Tests for WalletTUI app."""

    def test_tui_has_login_screen(self) -> None:
        """Test that TUI has login screen registered."""
        assert "login" in WalletTUI.SCREENS

    def test_tui_has_main_screen(self) -> None:
        """Test that TUI has main screen registered."""
        assert "main" in WalletTUI.SCREENS

    def test_tui_has_all_modal_screens(self) -> None:
        """Test that all modal screens are registered."""
        expected = {"order_buy", "order_sell", "transfer", "deposit", "withdraw"}
        assert expected.issubset(set(WalletTUI.SCREENS.keys()))

    def test_tui_initialization_with_base_url(self) -> None:
        """Test TUI initialization with custom base URL."""
        app = WalletTUI(base_url="http://test:9000")
        assert app.base_url == "http://test:9000"

    def test_tui_api_client_initialized(self) -> None:
        """Test that API client is initialized."""
        app = WalletTUI()
        assert app.api is not None

    def test_on_mount_with_initial_token_opens_main_screen(self) -> None:
        async def _run() -> None:
            app = WalletTUI(initial_token="session_123")
            app.api = FakeApi()
            async with app.run_test() as pilot:
                await pilot.pause()
                assert isinstance(app.screen, MainScreen)

        asyncio.run(_run())

    def test_connect_with_token(self) -> None:
        """Test connecting with a token."""
        app = WalletTUI()
        app.connect_with_token("test_token_123")
        assert app.api.config.token == "test_token_123"

    def test_connect_telegram_user(self) -> None:
        """Test connecting with Telegram user."""
        app = WalletTUI()

        with patch.object(app.api, 'auth_telegram') as mock_auth:
            mock_auth.return_value = {
                "token": "tg_token",
                "telegram_user_id": 123,
                "username": "testuser"
            }
            app.connect_telegram_user(123, "testuser")

            assert app.api.config.token == "tg_token"
            assert app.user_id == 123
            assert app.username == "testuser"

    def test_on_telegram_login_success(self) -> None:
        """Test Telegram login success callback."""
        app = WalletTUI()

        with patch.object(app, "push_screen") as mock_push:
            app.on_telegram_login_success({
                "session_token": "session_123",
                "user_id": 456,
                "username": "tguser"
            })

        assert app.api.config.token == "session_123"
        assert app.user_id == 456
        mock_push.assert_called_once_with("main")

    def test_refresh_screens_handles_no_refresh_method(self) -> None:
        """Test refresh_screens doesn't crash on screens without refresh_data."""
        app = WalletTUI()
        # Should not raise
        app.refresh_screens()


class TestOrdersScreen:
    """Tests for OrdersScreen."""

    def test_orders_screen_composes(self) -> None:
        """Test that OrdersScreen can be instantiated."""
        screen = OrdersScreen()
        assert screen is not None

    def test_orders_screen_has_escape_binding(self) -> None:
        """Test OrdersScreen has escape binding."""
        bindings = OrdersScreen.BINDINGS
        binding_keys = [b.key for b in bindings]
        assert "escape" in binding_keys


class TestPortfolioScreen:
    """Tests for PortfolioScreen."""

    def test_portfolio_screen_composes(self) -> None:
        """Test that PortfolioScreen can be instantiated."""
        screen = PortfolioScreen()
        assert screen is not None

    def test_portfolio_screen_loads_stats_and_table(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            app.api = FakeApi()

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                app.push_screen("portfolio")
                await pilot.pause()

                portfolio = app.screen
                assert isinstance(portfolio, PortfolioScreen)
                table = portfolio.query_one("#portfolio-table")
                assert getattr(table, "row_count", 0) >= 1

        asyncio.run(_run())


class TestRebalanceScreen:
    """Tests for RebalanceScreen."""

    def test_rebalance_screen_composes(self) -> None:
        """Test that RebalanceScreen can be instantiated."""
        screen = RebalanceScreen()
        assert screen is not None


class TestMainAnalytics:
    def test_main_screen_analytics_not_auto_called_on_refresh_or_selection(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            api = AdvisorTrackingApi()
            app.api = api

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)
                assert api.analysis_calls == 0

                main.refresh_data()
                await pilot.pause()
                assert api.analysis_calls == 0

                assets_table = main.query_one("#assets-table")
                assets_table.focus()
                assets_table.move_cursor(row=1, column=0, animate=False, scroll=False)
                await pilot.pause()
                assert api.analysis_calls == 0

                main.action_generate_analytics()
                await pilot.pause()
                assert api.analysis_calls >= 1

        asyncio.run(_run())

    def test_main_screen_analytics_generation_uses_selected_ticker(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            api = AdvisorTrackingApi()
            app.api = api

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)
                assets_table = main.query_one("#assets-table")
                assets_table.focus()
                assets_table.move_cursor(row=1, column=0, animate=False, scroll=False)
                await pilot.pause()
                main.action_generate_analytics()
                await pilot.pause()

                assert api.last_asset_id == "TSLAx"

        asyncio.run(_run())

    def test_main_screen_analytics_on_usdt_uses_tradeable_position(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            api = UsdtFirstAssetsApi()
            app.api = api

            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)
                assets_table = main.query_one("#assets-table")
                assets_table.focus()
                assets_table.move_cursor(row=0, column=0, animate=False, scroll=False)
                await pilot.pause()
                main.action_generate_analytics()
                await pilot.pause()

                assert api.last_asset_id == "AAPLx"

        asyncio.run(_run())

    def test_main_row_selected_uses_event_control_not_table(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            app.api = FakeApi()
            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                main = app.screen
                assert isinstance(main, MainScreen)
                assets_table = main.query_one("#assets-table")
                event = SimpleNamespace(control=assets_table, cursor_row=0)
                main.on_data_table_row_selected(event)  # type: ignore[arg-type]
                await pilot.pause()
                assert main.selected_asset == "AAPLx"

        asyncio.run(_run())


class TestOrdersSelection:
    def test_orders_row_selected_uses_event_control_not_table(self) -> None:
        async def _run() -> None:
            app = WalletTUI()
            app.api = FakeApi()
            async with app.run_test() as pilot:
                app.on_telegram_login_success({"session_token": "session_123", "user_id": 1})
                await pilot.pause()
                app.push_screen("orders")
                await pilot.pause()
                orders = app.screen
                assert isinstance(orders, OrdersScreen)
                table = orders.query_one("#orders-table")
                event = SimpleNamespace(control=table, cursor_row=0)
                orders.on_data_table_row_selected(event)  # type: ignore[arg-type]
                await pilot.pause()
                detail = orders.query_one("#order-detail")
                assert "Select an order row" in str(detail.render())

        asyncio.run(_run())
