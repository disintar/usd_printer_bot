"""API client for wallet service."""
from __future__ import annotations

import httpx
import logging
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ApiConfig:
    """API configuration."""
    base_url: str = "http://localhost:8000"
    token: str | None = None


@dataclass
class BotInfo:
    """Bot information."""
    username: str
    first_name: str
    bot_login_url: str


class UnauthorizedError(Exception):
    """Raised when API returns 401 Unauthorized."""


class WalletApi:
    """Client for the wallet API service."""

    def __init__(
        self,
        config: ApiConfig | None = None,
        on_unauthorized: Callable[[], None] | None = None,
    ) -> None:
        self.config = config or ApiConfig()
        self.client = httpx.Client(base_url=self.config.base_url, timeout=30.0)
        self.on_unauthorized = on_unauthorized

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Raise on non-2xx responses and trigger unauthorized callback for 401."""
        if response.status_code == 401:
            if self.on_unauthorized is not None:
                self.on_unauthorized()
            raise UnauthorizedError("Authentication required")
        response.raise_for_status()

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return headers

    def get_bot_info(self) -> BotInfo:
        """Get bot information from backend."""
        response = self.client.get("/bot/info")
        self._raise_for_status(response)
        data = response.json()["data"]
        
        return BotInfo(
            username=data["username"],
            first_name=data["first_name"],
            bot_login_url=data["bot_login_url"],
        )

    def auth_telegram(self, telegram_user_id: int, username: str = "") -> dict[str, Any]:
        """Authenticate via Telegram user ID."""
        response = self.client.post(
            "/auth/telegram",
            json={"telegram_user_id": telegram_user_id, "username": username},
            headers=self._headers(),
        )
        self._raise_for_status(response)
        data = response.json()
        if data.get("status") != "ok":
            raise ValueError(data.get("message", "Authentication failed"))
        return data["data"]

    def create_pending_auth(self) -> dict[str, Any]:
        """Create a pending auth token."""
        response = self.client.post("/auth/pending", json={})
        self._raise_for_status(response)
        return response.json()["data"]

    def check_pending_auth(self, token: str) -> dict[str, Any]:
        """Check pending auth status."""
        response = self.client.get(f"/auth/pending/{token}")
        self._raise_for_status(response)
        return response.json()

    def complete_auth(self, token: str, telegram_user_id: int) -> dict[str, Any]:
        """Complete pending auth with user ID."""
        response = self.client.post(
            "/auth/complete",
            json={"token": token, "telegram_user_id": telegram_user_id},
        )
        self._raise_for_status(response)
        return response.json()["data"]

    def auth_telegram_widget(self, widget_data: dict[str, Any]) -> dict[str, Any]:
        """Authenticate via Telegram Login Widget data."""
        response = self.client.post(
            "/auth/telegram/widget",
            json=widget_data,
            headers=self._headers(),
        )
        self._raise_for_status(response)
        data = response.json()
        if data.get("status") != "ok":
            raise ValueError(data.get("message", "Authentication failed"))
        result = data["data"]
        self.config.token = result["session_token"]
        return result

    def validate_session(self, session_token: str) -> dict[str, Any]:
        """Validate a session token."""
        response = self.client.get(
            f"/auth/session/{session_token}",
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return response.json()

    def get_balance(self) -> dict[str, Any]:
        """Get wallet balance."""
        response = self.client.get("/test/balance", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def get_address(self) -> dict[str, Any]:
        """Get wallet address."""
        response = self.client.get("/test/address", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def get_time(self) -> dict[str, Any]:
        """Get backend test server clock info."""
        response = self.client.get("/test/time", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def get_prices(self) -> dict[str, str]:
        """Get all asset prices."""
        response = self.client.get("/test/prices", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]["prices"]

    def get_assets(self) -> list[dict[str, Any]]:
        """Get all assets."""
        response = self.client.get("/test/assets", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]["assets"]

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        """Get asset detail."""
        response = self.client.get(f"/test/asset/{asset_id}", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def get_positions(self) -> list[dict[str, Any]]:
        """Get all positions."""
        response = self.client.get("/test/positions", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]["positions"]

    def get_orders(self) -> list[dict[str, Any]]:
        """Get all orders."""
        response = self.client.get("/test/orders", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]["orders"]

    def get_order(self, order_id: int) -> dict[str, Any]:
        """Get specific order."""
        response = self.client.get(f"/test/order/{order_id}", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def buy(self, asset_id: str, quantity: str) -> dict[str, Any]:
        """Place buy order."""
        response = self.client.post(
            "/test/buy",
            json={"asset_id": asset_id, "quantity": quantity},
            headers=self._headers(),
        )
        self._raise_for_status(response)
        data = response.json()
        if data.get("status") != "ok":
            raise ValueError(data.get("message", "Buy order failed"))
        return data["data"]

    def sell(self, asset_id: str, quantity: str) -> dict[str, Any]:
        """Place sell order."""
        response = self.client.post(
            "/test/sell",
            json={"asset_id": asset_id, "quantity": quantity},
            headers=self._headers(),
        )
        self._raise_for_status(response)
        data = response.json()
        if data.get("status") != "ok":
            raise ValueError(data.get("message", "Sell order failed"))
        return data["data"]

    def deposit(self, amount: str) -> dict[str, Any]:
        """Deposit funds."""
        response = self.client.post(
            "/test/deposit",
            json={"amount": amount},
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return response.json()["data"]

    def withdraw(self, amount: str) -> dict[str, Any]:
        """Withdraw funds."""
        response = self.client.post(
            "/test/withdraw",
            json={"amount": amount},
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return response.json()["data"]

    def transfer(self, to_telegram_user_id: int, amount: str) -> dict[str, Any]:
        """Transfer funds."""
        response = self.client.post(
            "/test/transfer",
            json={"to_telegram_user_id": to_telegram_user_id, "amount": amount},
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return response.json()["data"]

    def get_portfolio(self) -> dict[str, Any]:
        """Get portfolio summary."""
        response = self.client.get("/test/portfolio", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def get_risk(self) -> dict[str, Any]:
        """Get risk assessment."""
        response = self.client.get("/test/risk", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def rebalance(self) -> dict[str, Any]:
        """Get rebalance actions."""
        response = self.client.post("/test/rebalance", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def get_agents(self) -> dict[str, Any]:
        """Get AI agents info."""
        response = self.client.get("/test/agents", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def select_agents(self, selected_agents: list[str]) -> dict[str, Any]:
        """Select AI agents."""
        response = self.client.post(
            "/test/agents/select",
            json={"selected_agents": selected_agents},
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return response.json()["data"]

    def get_allocation(self) -> dict[str, Any]:
        """Get agent allocation."""
        response = self.client.get("/test/agents/allocation", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def update_allocation(self, allocation: dict[str, float]) -> dict[str, Any]:
        """Update agent allocation."""
        response = self.client.post(
            "/test/agents/allocation",
            json={"allocation": allocation},
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return response.json()["data"]

    def get_reasoning(self, asset_id: str) -> dict[str, Any]:
        """Get agent reasoning for asset."""
        response = self.client.get(
            f"/test/agents/reasoning?asset_id={asset_id}",
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return response.json()["data"]

    def get_advisors_list(self) -> list[dict[str, Any]]:
        """Get configured adviser personas."""
        response = self.client.get("/advisors/list", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]["advisors"]

    def get_advisor_preferences(self) -> dict[str, Any]:
        """Get selected advisers and risk profile."""
        response = self.client.get("/advisors/preferences", headers=self._headers())
        self._raise_for_status(response)
        return response.json()["data"]

    def update_advisor_preferences(self, selected_advisors: list[str], risk_profile: str) -> dict[str, Any]:
        """Update selected advisers and risk profile."""
        response = self.client.post(
            "/advisors/preferences",
            json={"selected_advisors": selected_advisors, "risk_profile": risk_profile},
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return response.json()["data"]

    def get_advisor_analysis(self, asset_id: str) -> dict[str, Any]:
        """Get adviser analysis for one ticker."""
        logger.info("WalletApi.get_advisor_analysis request asset_id=%s", asset_id)
        response = self.client.get("/advisors/analysis", params={"asset_id": asset_id}, headers=self._headers())
        if response.status_code >= 400:
            logger.warning(
                "WalletApi.get_advisor_analysis failed status=%s asset_id=%s body=%s",
                response.status_code,
                asset_id,
                response.text[:200],
            )
        self._raise_for_status(response)
        return response.json()["data"]

    def close(self) -> None:
        """Close the client."""
        self.client.close()
