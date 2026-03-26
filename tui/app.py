"""Main TUI application."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App

from .api import WalletApi, ApiConfig
from .session_store import SessionTokenStore
from .terminal_compat import TerminalCompatibilityService
from .screens import (
    LoginScreen,
    MainScreen,
    OrdersScreen,
    PortfolioScreen,
    RebalanceScreen,
)
from .modals import (
    OrderModal,
    TransferModal,
    DepositWithdrawModal,
)


class WalletTUI(App):
    """Main TUI application."""

    CSS = """
    Screen {
        background: $surface;
    }
    """

    # Register all screens
    SCREENS = {
        "login": LoginScreen,
        "main": MainScreen,
        "orders": OrdersScreen,
        "portfolio": PortfolioScreen,
        "rebalance": RebalanceScreen,
        "order_buy": lambda: OrderModal("buy"),
        "order_sell": lambda: OrderModal("sell"),
        "transfer": TransferModal,
        "deposit": lambda: DepositWithdrawModal("deposit"),
        "withdraw": lambda: DepositWithdrawModal("withdraw"),
    }

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        initial_token: str | None = None,
        session_file_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        TerminalCompatibilityService.apply()
        super().__init__(**kwargs)
        self.base_url = base_url
        token_store_path = Path(session_file_path) if session_file_path else None
        self.session_store = SessionTokenStore(token_file_path=token_store_path)
        resolved_token = initial_token if initial_token else self.session_store.load_token()
        self.api: WalletApi = WalletApi(
            ApiConfig(base_url=base_url, token=resolved_token),
            on_unauthorized=self.handle_unauthorized,
        )
        self.initial_token = resolved_token
        self.user_id: int = 0
        self.username: str = ""
        self._auth_reset_in_progress = False

    def connect_with_token(self, token: str) -> None:
        """Connect using an existing token."""
        self.api.config.token = token
        self.session_store.save_token(token)

    def connect_telegram_user(self, user_id: int, username: str = "") -> None:
        """Connect with Telegram user credentials."""
        try:
            result = self.api.auth_telegram(user_id, username)
            self.api.config.token = result["token"]
            self.session_store.save_token(result["token"])
            self.user_id = user_id
            self.username = username
        except Exception as e:
            raise ValueError(f"Connection failed: {e}")

    def on_telegram_login_success(self, data: dict[str, Any]) -> None:
        """Handle successful Telegram login."""
        session_token = data.get("session_token")
        if session_token:
            self.api.config.token = session_token
            self.session_store.save_token(session_token)
            self.user_id = data.get("user_id", 0)
            self.username = data.get("username", "")
            self.push_screen("main")

    def on_mount(self) -> None:
        """Set up screens on mount."""
        if self.api.config.token:
            self.push_screen("main")
            return
        self.push_screen("login")

    def handle_unauthorized(self) -> None:
        """Reset stale auth state and navigate back to Telegram login."""
        if self._auth_reset_in_progress:
            return
        self._auth_reset_in_progress = True
        self.api.config.token = None
        self.initial_token = None
        self.user_id = 0
        self.username = ""
        self.session_store.clear_token()
        self.switch_screen("login")
        self._auth_reset_in_progress = False

    def refresh_screens(self) -> None:
        """Refresh data on all visible main screens."""
        try:
            main_screen = self.get_screen("main")
            if hasattr(main_screen, "refresh_data"):
                main_screen.refresh_data()
            for screen in self.screen.stack:
                if hasattr(screen, "refresh_data"):
                    screen.refresh_data()
        except Exception:
            pass


def run_tui(base_url: str = "http://localhost:8000", token: str | None = None) -> None:
    """Run the wallet TUI application."""
    app = WalletTUI(base_url=base_url, initial_token=token)
    app.run()


if __name__ == "__main__":
    run_tui()
