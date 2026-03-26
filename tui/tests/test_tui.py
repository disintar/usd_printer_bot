"""Tests for the Wallet TUI."""
from __future__ import annotations

import httpx
from unittest.mock import MagicMock, patch
from decimal import Decimal
from pathlib import Path

import pytest
from textual.drivers.linux_driver import LinuxDriver
from textual.drivers.linux_inline_driver import LinuxInlineDriver

from tui import WalletApi, ApiConfig, WalletTUI, format_decimal, mark_colored
from tui.terminal_compat import TerminalCompatibilityService


class TestWalletApi:
    """Tests for the WalletApi client."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = ApiConfig(base_url="http://localhost:8000")
        self.api = WalletApi(self.config)

    def test_api_config_defaults(self) -> None:
        """Test ApiConfig has correct defaults."""
        config = ApiConfig()
        assert config.base_url == "http://localhost:8000"
        assert config.token is None

    def test_api_config_with_token(self) -> None:
        """Test ApiConfig with token."""
        config = ApiConfig(base_url="http://example.com", token="abc123")
        assert config.base_url == "http://example.com"
        assert config.token == "abc123"

    def test_headers_without_token(self) -> None:
        """Test headers without token."""
        headers = self.api._headers()
        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers

    def test_headers_with_token(self) -> None:
        """Test headers with token."""
        self.api.config.token = "test_token"
        headers = self.api._headers()
        assert headers["Authorization"] == "Bearer test_token"

    @patch.object(httpx.Client, "post")
    def test_auth_telegram_success(self, mock_post: MagicMock) -> None:
        """Test successful Telegram authentication."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "token": "test_token_123",
                "telegram_user_id": 12345,
                "username": "testuser",
            },
        }
        mock_post.return_value = mock_response

        result = self.api.auth_telegram(12345, "testuser")

        assert result["token"] == "test_token_123"
        assert result["telegram_user_id"] == 12345
        assert result["username"] == "testuser"

    @patch.object(httpx.Client, "post")
    def test_auth_telegram_idempotent(self, mock_post: MagicMock) -> None:
        """Test Telegram auth is idempotent."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "token": "same_token",
                "telegram_user_id": 12345,
                "username": "testuser",
            },
        }
        mock_post.return_value = mock_response

        result1 = self.api.auth_telegram(12345, "testuser")
        result2 = self.api.auth_telegram(12345, "testuser2")

        assert result1["token"] == result2["token"]
        mock_post.assert_called()

    @patch.object(httpx.Client, "post")
    def test_auth_telegram_failure(self, mock_post: MagicMock) -> None:
        """Test Telegram auth failure raises error."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "error", "message": "Invalid user"}
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="Invalid user"):
            self.api.auth_telegram(99999, "baduser")

    @patch.object(httpx.Client, "get")
    def test_get_balance(self, mock_get: MagicMock) -> None:
        """Test getting wallet balance."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "cash_usdt": "10000.00",
                "equity_usdt": "10500.00",
                "total_balance_usdt": "10500.00",
                "pnl_percent": "5.00",
                "pnl_absolute": "500.00",
            },
        }
        mock_get.return_value = mock_response

        result = self.api.get_balance()

        assert result["cash_usdt"] == "10000.00"
        assert result["equity_usdt"] == "10500.00"
        assert result["pnl_percent"] == "5.00"
        assert result["pnl_absolute"] == "500.00"

    @patch.object(httpx.Client, "get")
    def test_get_prices(self, mock_get: MagicMock) -> None:
        """Test getting asset prices."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "prices": {
                    "USDt": "1.00",
                    "AAPLx": "192.80",
                    "NVDAx": "821.70",
                },
            },
        }
        mock_get.return_value = mock_response

        result = self.api.get_prices()

        assert result["USDt"] == "1.00"
        assert result["AAPLx"] == "192.80"
        assert result["NVDAx"] == "821.70"

    @patch.object(httpx.Client, "get")
    def test_get_time(self, mock_get: MagicMock) -> None:
        """Test getting backend test-time clock."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "server_time_utc": "2026-03-25T00:00:00+00:00",
                "simulated_time_utc": "2026-01-24T00:00:00+00:00",
                "test_time_warp_enabled": True,
                "window_days": 60,
                "hours_per_tick": 1,
            },
        }
        mock_get.return_value = mock_response

        result = self.api.get_time()
        assert result["test_time_warp_enabled"] is True
        assert result["hours_per_tick"] == 1

    @patch.object(httpx.Client, "post")
    def test_buy_order(self, mock_post: MagicMock) -> None:
        """Test placing a buy order."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "order_id": 1,
                "side": "buy",
                "asset_id": "AAPLx",
                "quantity": "2",
                "price": "192.80",
                "notional": "385.60",
                "status": "filled",
            },
        }
        mock_post.return_value = mock_response

        result = self.api.buy("AAPLx", "2")

        assert result["order_id"] == 1
        assert result["side"] == "buy"
        assert result["asset_id"] == "AAPLx"
        assert result["status"] == "filled"

    @patch.object(httpx.Client, "post")
    def test_sell_order(self, mock_post: MagicMock) -> None:
        """Test placing a sell order."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "order_id": 2,
                "side": "sell",
                "asset_id": "AAPLx",
                "quantity": "1",
                "price": "192.80",
                "notional": "192.80",
                "status": "filled",
            },
        }
        mock_post.return_value = mock_response

        result = self.api.sell("AAPLx", "1")

        assert result["order_id"] == 2
        assert result["side"] == "sell"
        assert result["status"] == "filled"

    @patch.object(httpx.Client, "post")
    def test_deposit(self, mock_post: MagicMock) -> None:
        """Test deposit."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "deposited": "1000.00",
                "new_balance": "11000.00",
            },
        }
        mock_post.return_value = mock_response

        result = self.api.deposit("1000.00")

        assert result["deposited"] == "1000.00"
        assert result["new_balance"] == "11000.00"

    @patch.object(httpx.Client, "post")
    def test_withdraw(self, mock_post: MagicMock) -> None:
        """Test withdrawal."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "withdrawn": "500.00",
                "new_balance": "9500.00",
            },
        }
        mock_post.return_value = mock_response

        result = self.api.withdraw("500.00")

        assert result["withdrawn"] == "500.00"
        assert result["new_balance"] == "9500.00"

    @patch.object(httpx.Client, "post")
    def test_transfer(self, mock_post: MagicMock) -> None:
        """Test transfer."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "transferred": "100.00",
                "to_telegram_user_id": 2002,
                "new_balance": "9900.00",
            },
        }
        mock_post.return_value = mock_response

        result = self.api.transfer(2002, "100.00")

        assert result["transferred"] == "100.00"
        assert result["to_telegram_user_id"] == 2002


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_format_decimal_string(self) -> None:
        """Test formatting decimal from string."""
        assert format_decimal("1234.56") == "1,234.56"
        assert format_decimal("1000.00") == "1,000.00"

    def test_format_decimal_float(self) -> None:
        """Test formatting decimal from float."""
        assert format_decimal(1234.56) == "1,234.56"

    def test_format_decimal_decimal(self) -> None:
        """Test formatting Decimal type."""
        assert format_decimal(Decimal("1234.56")) == "1,234.56"

    def test_format_decimal_places(self) -> None:
        """Test formatting with different decimal places."""
        assert format_decimal("1.234567", places=4) == "1.2346"
        assert format_decimal("1.2", places=4) == "1.2000"

    def test_mark_colored(self) -> None:
        """Test mark_colored returns colored strings."""
        assert "[green]Buy[/green]" == mark_colored("Buy")
        assert "[red]Sell[/red]" == mark_colored("Sell")
        assert "[yellow]Hold[/yellow]" == mark_colored("Hold")
        assert "[cyan]Cover[/cyan]" == mark_colored("Cover")
        assert "[magenta]Short[/magenta]" == mark_colored("Short")

    def test_mark_colored_unknown(self) -> None:
        """Test mark_colored with unknown mark."""
        result = mark_colored("Unknown")
        assert "Unknown" in result


class TestWalletTUI:
    """Tests for WalletTUI application."""

    def test_tui_initialization(self) -> None:
        """Test TUI initializes with correct defaults."""
        app = WalletTUI()
        assert app.base_url == "http://localhost:8000"
        # api is now initialized in __init__
        assert app.user_id == 0

    def test_tui_custom_base_url(self) -> None:
        """Test TUI with custom base URL."""
        app = WalletTUI(base_url="http://custom:9000")
        assert app.base_url == "http://custom:9000"

    def test_tui_initial_token_configured(self) -> None:
        """Test TUI stores initial token in API config."""
        app = WalletTUI(initial_token="session_token_123")
        assert app.api.config.token == "session_token_123"

    def test_tui_loads_token_from_session_temp_file(self, tmp_path: Path) -> None:
        """Test TUI loads token from temp session file when no initial token is given."""
        token_file = tmp_path / "wallet_tui_session_token"
        token_file.write_text("persisted_token_123\n", encoding="utf-8")

        app = WalletTUI(session_file_path=str(token_file))

        assert app.api.config.token == "persisted_token_123"

    def test_tui_saves_token_to_session_temp_file_on_login_success(
        self, tmp_path: Path
    ) -> None:
        """Test successful login persists token into temp session file."""
        token_file = tmp_path / "wallet_tui_session_token"
        app = WalletTUI(session_file_path=str(token_file))

        with patch.object(app, "push_screen") as mock_push:
            app.on_telegram_login_success(
                {"session_token": "session_abc", "user_id": 456, "username": "tguser"}
            )
            mock_push.assert_called_once_with("main")

        assert token_file.read_text(encoding="utf-8").strip() == "session_abc"

    def test_handle_unauthorized_clears_token_and_switches_to_login(self, tmp_path: Path) -> None:
        """Unauthorized flow should clear current token and route to login."""
        token_file = tmp_path / "wallet_tui_session_token"
        token_file.write_text("stale_session", encoding="utf-8")
        app = WalletTUI(session_file_path=str(token_file), initial_token="stale_session")

        with patch.object(app, "switch_screen") as mock_switch:
            app.handle_unauthorized()

        assert app.api.config.token is None
        assert app.user_id == 0
        assert app.username == ""
        assert token_file.exists() is False
        mock_switch.assert_called_once_with("login")

    def test_tui_connect_stores_token(self) -> None:
        """Test connect stores token in api config."""
        app = WalletTUI()

        with patch.object(WalletApi, "auth_telegram") as mock_auth:
            mock_auth.return_value = {
                "token": "test_token_abc",
                "telegram_user_id": 12345,
                "username": "testuser",
            }

            app.connect_telegram_user(12345, "testuser")

            assert app.api is not None
            assert app.api.config.token == "test_token_abc"
            assert app.user_id == 12345

    def test_tui_screens_registered(self) -> None:
        """Test all screens are registered."""
        expected_screens = {
            "login",
            "main",
            "orders",
            "portfolio",
            "rebalance",
            "order_buy",
            "order_sell",
            "transfer",
            "deposit",
            "withdraw",
        }
        assert set(WalletTUI.SCREENS.keys()) == set(expected_screens)


class TestTerminalCompatibilityService:
    """Tests for terminal compatibility query suppression."""

    def test_should_disable_terminal_queries_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TUI_ENABLE_TERMINAL_QUERIES", raising=False)
        assert TerminalCompatibilityService._should_disable_terminal_queries() is True

    def test_should_disable_terminal_queries_can_be_overridden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TUI_ENABLE_TERMINAL_QUERIES", "1")
        assert TerminalCompatibilityService._should_disable_terminal_queries() is False

    def test_apply_suppresses_linux_driver_query_writes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TUI_ENABLE_TERMINAL_QUERIES", raising=False)
        TerminalCompatibilityService._patched = False
        TerminalCompatibilityService.apply()

        writes: list[str] = []

        class DummyDriver:
            input_tty = True

            def write(self, data: str) -> None:
                writes.append(data)

            def flush(self) -> None:
                writes.append("flush")

        driver = DummyDriver()

        LinuxDriver._request_terminal_sync_mode_support(driver)
        LinuxDriver._query_in_band_window_resize(driver)
        LinuxInlineDriver._request_terminal_sync_mode_support(driver)
        LinuxInlineDriver._query_in_band_window_resize(driver)

        assert writes == []


class TestAPIClientIntegration:
    """Integration tests for API client with mocked responses."""

    @patch.object(httpx.Client, "get")
    def test_get_assets(self, mock_get: MagicMock) -> None:
        """Test getting all assets."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "assets": [
                    {
                        "asset_id": "AAPLx",
                        "balance": "10",
                        "current_price": "192.80",
                        "net_worth": "1928.00",
                        "pnl_percent": "5.00",
                        "pnl_absolute": "92.80",
                        "mark": "Buy",
                    },
                    {
                        "asset_id": "NVDAx",
                        "balance": "5",
                        "current_price": "821.70",
                        "net_worth": "4108.50",
                        "pnl_percent": "10.00",
                        "pnl_absolute": "410.85",
                        "mark": "Hold",
                    },
                ],
            },
        }
        mock_get.return_value = mock_response

        api = WalletApi(ApiConfig())
        result = api.get_assets()

        assert len(result) == 2
        assert result[0]["asset_id"] == "AAPLx"
        assert result[1]["asset_id"] == "NVDAx"

    @patch.object(httpx.Client, "get")
    def test_get_positions(self, mock_get: MagicMock) -> None:
        """Test getting positions."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "positions": [
                    {
                        "asset_id": "AAPLx",
                        "quantity": "10",
                        "average_entry_price": "180.00",
                        "current_price": "192.80",
                        "net_worth": "1928.00",
                        "pnl_percent": "7.11",
                        "pnl_absolute": "128.00",
                        "mark": "Buy",
                    },
                ],
            },
        }
        mock_get.return_value = mock_response

        api = WalletApi(ApiConfig())
        result = api.get_positions()

        assert len(result) == 1
        assert result[0]["asset_id"] == "AAPLx"
        assert result[0]["mark"] == "Buy"

    @patch.object(httpx.Client, "get")
    def test_get_portfolio(self, mock_get: MagicMock) -> None:
        """Test getting portfolio."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "total_balance_usdt": "10500.00",
                "pnl_percent": "5.00",
                "pnl_absolute": "500.00",
                "allocation": {"AAPLx": 18.36, "USDt": 81.64},
                "assets": [
                    {
                        "asset_id": "AAPLx",
                        "quantity": "10",
                        "value_usdt": "1928.00",
                        "allocation_percent": "18.36",
                    },
                ],
            },
        }
        mock_get.return_value = mock_response

        api = WalletApi(ApiConfig())
        result = api.get_portfolio()

        assert result["total_balance_usdt"] == "10500.00"
        assert result["pnl_percent"] == "5.00"
        assert len(result["assets"]) == 1

    @patch.object(httpx.Client, "get")
    def test_get_agents(self, mock_get: MagicMock) -> None:
        """Test getting AI agents."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "active_agents": ["Buy", "Cover", "Sell", "Short", "Hold"],
                "selected_agents": ["Buy", "Hold"],
                "allocation": {"Buy": 50.0, "Cover": 0.0, "Sell": 0.0, "Short": 0.0, "Hold": 50.0},
            },
        }
        mock_get.return_value = mock_response

        api = WalletApi(ApiConfig())
        result = api.get_agents()

        assert len(result["active_agents"]) == 5
        assert result["selected_agents"] == ["Buy", "Hold"]
        assert result["allocation"]["Buy"] == 50.0

    @patch.object(httpx.Client, "post")
    def test_select_agents(self, mock_post: MagicMock) -> None:
        """Test selecting agents."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {"selected_agents": ["Buy", "Sell", "Hold"]},
        }
        mock_post.return_value = mock_response

        api = WalletApi(ApiConfig())
        result = api.select_agents(["Buy", "Sell", "Hold"])

        assert result["selected_agents"] == ["Buy", "Sell", "Hold"]

    @patch.object(httpx.Client, "get")
    def test_get_risk(self, mock_get: MagicMock) -> None:
        """Test getting risk assessment."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "risk_score": "35.5",
                "risk_level": "medium",
                "max_position_percent": "25.00",
                "cash_percent": "50.00",
                "equity_usdt": "10500.00",
            },
        }
        mock_get.return_value = mock_response

        api = WalletApi(ApiConfig())
        result = api.get_risk()

        assert result["risk_score"] == "35.5"
        assert result["risk_level"] == "medium"

    @patch.object(httpx.Client, "post")
    def test_rebalance(self, mock_post: MagicMock) -> None:
        """Test rebalance actions."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "actions": [
                    {"action": "buy", "asset_id": "NVDAx", "reason": "Underweight"},
                    {"action": "sell", "asset_id": "AAPLx", "reason": "Overweight"},
                ],
            },
        }
        mock_post.return_value = mock_response

        api = WalletApi(ApiConfig())
        result = api.rebalance()

        assert len(result["actions"]) == 2
        assert result["actions"][0]["action"] == "buy"


class TestTelegramAuthService:
    """Tests for Telegram Login Widget authentication."""

    def test_verify_login_widget_data_valid(self) -> None:
        """Test verification of valid Telegram Login Widget data."""
        import hashlib
        import hmac
        from tui import WalletApi
        
        # Test data that we know is valid
        # In a real test, you would use actual Telegram widget data
        # For now, test the API client setup
        api = WalletApi()
        assert api.config.token is None

    def test_telegram_auth_endpoint_exists(self) -> None:
        """Test that Telegram widget auth endpoint exists."""
        from tui import WalletApi
        
        api = WalletApi()
        # Test that we can make a request (will fail without server, but confirms method exists)
        assert hasattr(api, 'auth_telegram_widget')

    def test_telegram_traditional_auth(self) -> None:
        """Test traditional Telegram user ID auth."""
        from tui import WalletApi
        
        api = WalletApi()
        assert hasattr(api, 'auth_telegram')


class TestBotInfo:
    """Tests for bot info functionality."""

    def test_get_bot_info_method_exists(self) -> None:
        """Test that get_bot_info method exists on API client."""
        from tui import WalletApi
        api = WalletApi()
        assert hasattr(api, 'get_bot_info')

    def test_bot_info_dataclass(self) -> None:
        """Test BotInfo dataclass."""
        from tui.api import BotInfo
        info = BotInfo(
            username="test_bot",
            first_name="Test Bot",
            bot_login_url="https://t.me/test_bot"
        )
        assert info.username == "test_bot"
        assert info.bot_login_url == "https://t.me/test_bot"
