import json
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from django.test import Client, TestCase
from django.test.utils import override_settings

from wallet.constants import TEST_PRICES
from wallet.models import AgentPreference
from wallet.services.test_time_warp import TestTimeWarpService


class WalletApiTests(TestCase):
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

    def _auth(self, telegram_user_id: int = 1001) -> str:
        response = self._post(
            "/auth/telegram",
            {"telegram_user_id": telegram_user_id, "username": f"user{telegram_user_id}"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        return body["data"]["token"]

    def _auth_via_pending_flow(self, telegram_user_id: int = 3001) -> str:
        create = self._post("/auth/pending", {})
        self.assertEqual(create.status_code, 200)
        pending_token = create.json()["data"]["token"]

        complete = self._post(
            "/auth/complete",
            {"token": pending_token, "telegram_user_id": telegram_user_id},
        )
        self.assertEqual(complete.status_code, 200)
        return complete.json()["data"]["session_token"]

    def test_health_and_ws_endpoints_work(self) -> None:
        health_response = self._get("/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["status"], "ok")

        ws_response = self._get("/ws")
        self.assertEqual(ws_response.status_code, 200)
        self.assertEqual(ws_response.json()["status"], "ok")
        self.assertTrue(ws_response.json()["data"]["test_mode"])

    def test_advisors_list_endpoint_returns_configured_advisors(self) -> None:
        response = self._get("/advisors/list")
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["status"], "ok")

        advisors = body["data"]["advisors"]
        self.assertGreaterEqual(len(advisors), 10)

        first = advisors[0]
        self.assertEqual(first["name"], "Warren Buffett")
        self.assertEqual(first["category"], "serious")
        self.assertEqual(first["role"], "Long-term value investor")
        self.assertIn("value", first["tags"])
        self.assertIn("primary_tag", first)
        self.assertIn(
            first["primary_tag"],
            ["investments", "business", "books", "films", "anime", "games"],
        )
        self.assertTrue(
            all(
                advisor["primary_tag"] in ["investments", "business", "books", "films", "anime", "games"]
                for advisor in advisors
            )
        )

        by_id = {advisor["id"]: advisor for advisor in advisors}
        self.assertEqual(by_id["v"]["name"], "V (V for Vendetta)")
        self.assertEqual(by_id["wolf"]["name"], "Wolf (Wall Street)")
        self.assertEqual(by_id["v_cyberpunk"]["name"], "V (Cyberpunk 2077)")
        self.assertTrue(
            {"investments", "business", "books", "films", "anime", "games"}.issubset(
                {advisor["primary_tag"] for advisor in advisors}
            )
        )

    def test_advisors_list_supports_primary_tag_filter(self) -> None:
        response = self._get("/advisors/list?primary_tag=anime")
        self.assertEqual(response.status_code, 200)
        advisors = response.json()["data"]["advisors"]
        self.assertGreater(len(advisors), 0)
        self.assertTrue(all(advisor["primary_tag"] == "anime" for advisor in advisors))

    def test_advisors_list_rejects_invalid_primary_tag(self) -> None:
        response = self._get("/advisors/list?primary_tag=crypto")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid primary_tag", response.json()["message"])

    def test_agents_active_endpoint_works(self) -> None:
        response = self._get("/agents/active")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertIn("agents_active", response.json()["data"])

    def test_advisor_preferences_can_be_read_and_updated(self) -> None:
        token = self._auth()

        initial = self._get("/advisors/preferences", token)
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.json()["data"]["risk_profile"], "medium")
        self.assertFalse(initial.json()["data"]["onboarding_completed"])

        updated = self._post(
            "/advisors/preferences",
            {
                "selected_advisors": ["warren_buffett", "pavel_durov"],
                "risk_profile": "low",
            },
            token,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["data"]["risk_profile"], "low")
        self.assertEqual(
            updated.json()["data"]["selected_advisors"],
            ["warren_buffett", "pavel_durov"],
        )
        self.assertEqual(
            updated.json()["data"]["advisor_weights"],
            {"warren_buffett": 50.0, "pavel_durov": 50.0},
        )
        self.assertFalse(updated.json()["data"]["onboarding_completed"])

        agents_response = self._get("/test/agents", token)
        self.assertEqual(agents_response.status_code, 200)
        agents_data = agents_response.json()["data"]
        self.assertEqual(
            agents_data["selected_agents"],
            ["warren_buffett", "pavel_durov"],
        )
        self.assertEqual(
            agents_data["allocation"],
            {"warren_buffett": 50.0, "pavel_durov": 50.0},
        )

    @patch("wallet.views.advisors.AdvisorRecommendationsService.get_start_recommendations")
    def test_advisor_start_marks_onboarding_completed(self, mock_start) -> None:
        token = self._auth()
        mock_start.return_value = {
            "buy_recommendations": [
                {
                    "asset_id": "AAPLx",
                    "allocation_percent": "100.00",
                    "verdict": "buy",
                    "reason": "Mock rationale",
                }
            ],
            "advisor_summaries": [
                {"advisor_id": "warren_buffett", "summary": "Mock summary"},
            ],
        }

        response = self._post("/advisors/start", {"deposit_amount": "100"}, token)
        self.assertEqual(response.status_code, 200)

        profile = self._get("/advisors/preferences", token)
        self.assertEqual(profile.status_code, 200)
        self.assertTrue(profile.json()["data"]["onboarding_completed"])

    def test_onboarding_reset_clears_only_agent_choices(self) -> None:
        token = self._auth()
        self._post(
            "/advisors/preferences",
            {
                "selected_advisors": ["warren_buffett", "pavel_durov", "ray_dalio"],
                "advisor_weights": {
                    "warren_buffett": 60.0,
                    "pavel_durov": 25.0,
                    "ray_dalio": 15.0,
                },
                "risk_profile": "low",
            },
            token,
        )
        preference = AgentPreference.objects.get(account__identity__token=token)
        preference.onboarding_completed = True
        preference.initial_portfolio = {"buy_recommendations": [{"asset_id": "AAPLx"}]}
        preference.save(update_fields=["onboarding_completed", "initial_portfolio", "updated_at"])

        reset = self._post("/advisors/onboarding/reset", {}, token)
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(
            reset.json()["data"]["selected_advisors"],
            AgentPreference.default_selected_advisors(),
        )
        self.assertEqual(
            reset.json()["data"]["advisor_weights"],
            AgentPreference.default_advisor_weights(),
        )
        self.assertEqual(reset.json()["data"]["risk_profile"], "low")
        self.assertFalse(reset.json()["data"]["onboarding_completed"])

        updated_preference = AgentPreference.objects.get(account__identity__token=token)
        self.assertEqual(updated_preference.initial_portfolio, {})

        agents_response = self._get("/test/agents", token)
        self.assertEqual(agents_response.status_code, 200)
        self.assertEqual(
            agents_response.json()["data"]["selected_agents"],
            AgentPreference.default_selected_advisors(),
        )
        self.assertEqual(
            agents_response.json()["data"]["allocation"],
            AgentPreference.default_advisor_weights(),
        )

    def test_advisor_preferences_reject_invalid_weights(self) -> None:
        token = self._auth()
        response = self._post(
            "/advisors/preferences",
            {
                "selected_advisors": ["warren_buffett", "pavel_durov"],
                "advisor_weights": {"warren_buffett": 60.0, "pavel_durov": 30.0},
                "risk_profile": "medium",
            },
            token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")

    def test_advisor_preferences_reject_more_than_three_advisors(self) -> None:
        token = self._auth()
        response = self._post(
            "/advisors/preferences",
            {
                "selected_advisors": [
                    "warren_buffett",
                    "pavel_durov",
                    "ray_dalio",
                    "elon_musk",
                ],
                "advisor_weights": {
                    "warren_buffett": 25.0,
                    "pavel_durov": 25.0,
                    "ray_dalio": 25.0,
                    "elon_musk": 25.0,
                },
                "risk_profile": "medium",
            },
            token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("at most 3 advisors", response.json()["message"])

    @patch("wallet.views.advisors.AdvisorRecommendationsService.get_start_recommendations")
    def test_advisor_start_endpoint_returns_mocked_recommendation(self, mock_start) -> None:
        token = self._auth()
        mock_start.return_value = {
            "buy_recommendations": [
                {
                    "asset_id": "AAPLx",
                    "allocation_percent": "100.00",
                    "verdict": "buy",
                    "reason": "Mock rationale",
                }
            ],
            "advisor_summaries": [
                {"advisor_id": "warren_buffett", "summary": "Mock summary"},
            ]
        }

        response = self._post("/advisors/start", {"deposit_amount": "100"}, token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["buy_recommendations"][0]["asset_id"], "AAPLx")

    @patch("wallet.views.advisors.AdvisorRecommendationsService.get_start_recommendations")
    def test_advisor_start_endpoint_passes_risk_profile_override(self, mock_start) -> None:
        token = self._auth()
        mock_start.return_value = {
            "buy_recommendations": [
                {
                    "asset_id": "AAPLx",
                    "allocation_percent": "100.00",
                    "verdict": "buy",
                    "reason": "Mock rationale",
                }
            ],
            "advisor_summaries": [
                {"advisor_id": "warren_buffett", "summary": "Mock summary"},
            ],
        }

        response = self._post(
            "/advisors/start",
            {"deposit_amount": "100", "risk_profile": "high"},
            token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_start.call_args.kwargs["risk_profile_override"], "high")

    def test_advisor_start_endpoint_rejects_invalid_risk_profile(self) -> None:
        token = self._auth()
        response = self._post(
            "/advisors/start",
            {"deposit_amount": "100", "risk_profile": "ultra"},
            token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")

    @patch("wallet.views.advisors.AdvisorRecommendationsService.get_saved_start_recommendations")
    def test_advisor_start_get_returns_saved_initial_portfolio(self, mock_saved_start) -> None:
        token = self._auth()
        mock_saved_start.return_value = {
            "buy_recommendations": [
                {
                    "asset_id": "NVDAx",
                    "allocation_percent": "100.00",
                    "verdict": "buy",
                    "reason": "Saved recommendation",
                }
            ],
            "advisor_summaries": [
                {"advisor_id": "warren_buffett", "summary": "Saved summary"},
            ],
        }

        response = self._get("/advisors/start", token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["buy_recommendations"][0]["asset_id"], "NVDAx")

    @patch("wallet.views.advisors.AdvisorRecommendationsService.get_saved_start_recommendations")
    def test_advisor_start_get_returns_404_when_not_initialized(self, mock_saved_start) -> None:
        token = self._auth()
        mock_saved_start.return_value = None

        response = self._get("/advisors/start", token)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["status"], "error")

    @patch("wallet.views.advisors.AdvisorRecommendationsService.get_portfolio_recommendations")
    def test_advisor_portfolio_recommendations_endpoint_returns_mocked_actions(self, mock_recommendations) -> None:
        token = self._auth()
        mock_recommendations.return_value = {
            "actions": [
                {
                    "asset_id": "AAPLx",
                    "action": "hold",
                    "reason": "Hold mock",
                }
            ],
        }

        response = self._post("/advisors/recommendations", {}, token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["actions"][0]["action"], "hold")

    @patch("wallet.views.advisors.AdvisorRecommendationsService.get_asset_analysis")
    def test_advisor_asset_analysis_endpoint_returns_mocked_payload(self, mock_analysis) -> None:
        token = self._auth()
        mock_analysis.return_value = {
            "asset_id": "AAPLx",
            "recommendation": "buy",
            "summary": "Attractive valuation vs. growth profile.",
            "advisor_notes": [
                {"advisor_id": "warren_buffett", "name": "Warren Buffett", "thought": "Strong moat."},
                {"advisor_id": "pavel_durov", "name": "Pavel Durov", "thought": "Product momentum."},
            ],
        }

        response = self._get("/advisors/analysis?asset_id=AAPLx", token)
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["asset_id"], "AAPLx")
        self.assertEqual(payload["recommendation"], "buy")
        self.assertEqual(len(payload["advisor_notes"]), 2)

    @override_settings(MCP_ENABLED=False, OPENAI_API_KEY="", OPENAI_BASE_URL="")
    def test_advisor_asset_analysis_endpoint_returns_503_without_mcp_llm(self) -> None:
        token = self._auth()
        response = self._get("/advisors/analysis?asset_id=AAPLx", token)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")

    def test_auth_telegram_happy_path_and_idempotent(self) -> None:
        first = self._post("/auth/telegram", {"telegram_user_id": 12345, "username": "alice"})
        second = self._post("/auth/telegram", {"telegram_user_id": 12345, "username": "alice2"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        first_body = first.json()
        second_body = second.json()
        self.assertEqual(first_body["status"], "ok")
        self.assertEqual(second_body["status"], "ok")
        self.assertEqual(first_body["data"]["token"], second_body["data"]["token"])

    def test_auth_telegram_validation_failure(self) -> None:
        response = self._post("/auth/telegram", {"username": "missing_id"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")

    def test_pending_auth_complete_flow_and_status_checks(self) -> None:
        create_response = self._post("/auth/pending", {})
        self.assertEqual(create_response.status_code, 200)
        pending_token = create_response.json()["data"]["token"]
        self.assertTrue(pending_token)

        pending_status = self._get(f"/auth/pending/{pending_token}")
        self.assertEqual(pending_status.status_code, 200)
        self.assertEqual(pending_status.json()["data"]["status"], "pending")

        complete_response = self._post(
            "/auth/complete",
            {"token": pending_token, "telegram_user_id": 424242},
        )
        self.assertEqual(complete_response.status_code, 200)
        session_token = complete_response.json()["data"]["session_token"]
        self.assertTrue(session_token)

        completed_status = self._get(f"/auth/pending/{pending_token}")
        self.assertEqual(completed_status.status_code, 200)
        completed_data = completed_status.json()["data"]
        self.assertEqual(completed_data["status"], "completed")
        self.assertEqual(completed_data["telegram_user_id"], 424242)
        self.assertEqual(completed_data["session_token"], session_token)

    def test_pending_auth_not_found(self) -> None:
        response = self._get("/auth/pending/not_a_real_token")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["status"], "error")

    def test_session_validate_success_and_failure(self) -> None:
        session_token = self._auth_via_pending_flow(5151)

        valid = self._get(f"/auth/session/{session_token}")
        self.assertEqual(valid.status_code, 200)
        self.assertTrue(valid.json()["data"]["valid"])
        self.assertEqual(valid.json()["data"]["user_id"], 5151)

        invalid = self._get("/auth/session/not_valid")
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.json()["status"], "error")

    def test_session_token_can_access_protected_test_endpoints(self) -> None:
        session_token = self._auth_via_pending_flow(6161)
        self.assertTrue(session_token.startswith("session_"))

        balance_response = self._get("/test/balance", session_token)
        self.assertEqual(balance_response.status_code, 200)
        self.assertEqual(balance_response.json()["status"], "ok")

    def test_session_token_is_persisted_in_database(self) -> None:
        from wallet.services.auth_sessions import AuthSession

        session_token = self._auth_via_pending_flow(8080)
        self.assertTrue(AuthSession.objects.filter(session_token=session_token).exists())

        # Backward compatibility: validate endpoint accepts legacy raw token without prefix.
        if session_token.startswith("session_"):
            legacy_raw = session_token[len("session_"):]
            valid = self._get(f"/auth/session/{legacy_raw}")
            self.assertEqual(valid.status_code, 200)
            self.assertTrue(valid.json()["data"]["valid"])

    @patch("wallet.services.advisor_marks.AdvisorRecommendationsService.get_portfolio_recommendations")
    def test_positions_use_advisor_marks_and_thoughts(self, mock_recommendations) -> None:
        token = self._auth()
        self._post("/test/buy", {"asset_id": "AAPLx", "quantity": "1"}, token)

        mock_recommendations.return_value = {
            "actions": [
                {
                    "asset_id": "AAPLx",
                    "action": "sell",
                    "reason": "Advisor sees weakening momentum.",
                }
            ],
        }

        response = self._get("/test/positions", token)
        self.assertEqual(response.status_code, 200)
        positions = response.json()["data"]["positions"]
        self.assertGreaterEqual(len(positions), 1)
        self.assertEqual(positions[0]["asset_id"], "AAPLx")
        self.assertEqual(positions[0]["mark"], "Sell")
        self.assertEqual(positions[0]["advisor_thought"], "Advisor sees weakening momentum.")

    @patch("wallet.services.assets.AdvisorMarksService.get_marks_and_thoughts")
    @patch("wallet.services.assets.MarketSignalsService.safe_asset_marks")
    def test_assets_use_market_marks_without_advisor_recommendations(
        self,
        mock_safe_asset_marks,
        mock_get_marks_and_thoughts,
    ) -> None:
        token = self._auth()
        mock_safe_asset_marks.return_value = {"TSLAx": "Buy"}

        response = self._get("/test/assets", token)
        self.assertEqual(response.status_code, 200)
        assets = response.json()["data"]["assets"]
        tsla = next(item for item in assets if item["asset_id"] == "TSLAx")
        self.assertEqual(tsla["mark"], "Buy")
        mock_get_marks_and_thoughts.assert_not_called()

    def test_complete_auth_invalid_token(self) -> None:
        response = self._post(
            "/auth/complete",
            {"token": "does-not-exist", "telegram_user_id": 123},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")

    def test_auth_required_for_test_endpoints(self) -> None:
        response = self._get("/test/balance")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["status"], "error")

    def test_auth_required_for_all_protected_routes(self) -> None:
        protected_get_routes = [
            "/test/balance",
            "/test/address",
            "/test/time",
            "/test/assets",
            "/test/asset/AAPLx",
            "/test/positions",
            "/test/order/1",
            "/test/orders",
            "/test/prices",
            "/test/agents",
            "/test/agents/allocation",
            "/test/agents/reasoning?asset_id=AAPLx",
            "/advisors/preferences",
            "/advisors/start",
            "/advisors/analysis?asset_id=AAPLx",
            "/test/portfolio",
            "/test/risk",
        ]
        protected_post_routes = [
            "/test/deposit",
            "/test/withdraw",
            "/test/transfer",
            "/test/buy",
            "/test/sell",
            "/test/agents/select",
            "/test/agents/allocation",
            "/advisors/preferences",
            "/advisors/start",
            "/advisors/recommendations",
            "/test/rebalance",
        ]

        for path in protected_get_routes:
            response = self._get(path)
            self.assertEqual(response.status_code, 401, path)

        for path in protected_post_routes:
            response = self._post(path, {})
            self.assertEqual(response.status_code, 401, path)

    def test_health_ws_and_bot_info_endpoints(self) -> None:
        health_response = self._get("/health")
        self.assertEqual(health_response.status_code, 200)

        ws_response = self._get("/ws")
        self.assertEqual(ws_response.status_code, 200)
        self.assertTrue(ws_response.json()["data"]["test_mode"])

        mock_telegram_payload = {
            "ok": True,
            "result": {"username": "wallet_tui_bot", "first_name": "Wallet TUI Bot"},
        }
        with patch("wallet.views.bot.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = mock_telegram_payload
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            bot_info_response = self._get("/bot/info")

        self.assertEqual(bot_info_response.status_code, 200)
        bot_data = bot_info_response.json()["data"]
        self.assertEqual(bot_data["username"], "wallet_tui_bot")
        self.assertIn("https://t.me/", bot_data["bot_login_url"])

    def test_auth_telegram_widget_success_with_mocked_verifier(self) -> None:
        class FakeUser:
            user_id = 7007
            username = "widget_user"

        with patch("wallet.views.auth.TelegramAuthService.verify_login_widget_data", return_value=FakeUser()):
            response = self._post(
                "/auth/telegram/widget",
                {"id": "7007", "username": "widget_user", "auth_date": "1", "hash": "fake"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["session_token"])
        self.assertEqual(data["user_id"], 7007)

    def test_supported_assets_constant_and_prices(self) -> None:
        token = self._auth()
        response = self._get("/test/prices", token)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        expected_assets = {
            "USDt",
            "TSLAx",
            "HOODx",
            "AMZNx",
            "NVDAx",
            "COINx",
            "GOOGLx",
            "AAPLx",
            "MSTRx",
        }
        self.assertEqual(set(data["prices"].keys()), expected_assets)
        self.assertEqual(data["prices"]["USDt"], "1")

    def test_balance_contains_required_pnl_fields(self) -> None:
        token = self._auth()
        response = self._get("/test/balance", token)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertIn("cash_usdt", data)
        self.assertIn("equity_usdt", data)
        self.assertIn("total_balance_usdt", data)
        self.assertIn("pnl_percent", data)
        self.assertIn("pnl_absolute", data)

    @override_settings(TEST_TIME_WARP_ENABLED=True)
    def test_test_time_endpoint_returns_backend_clock_and_advances(self) -> None:
        token = self._auth()
        TestTimeWarpService.reset_runtime_state()

        first = self._get("/test/time", token)
        self.assertEqual(first.status_code, 200)
        first_data = first.json()["data"]
        self.assertIn("server_time_utc", first_data)
        self.assertIn("simulated_time_utc", first_data)
        self.assertTrue(first_data["test_time_warp_enabled"])

        TestTimeWarpService.advance_and_sync_prices()
        second = self._get("/test/time", token)
        self.assertEqual(second.status_code, 200)
        second_data = second.json()["data"]
        self.assertNotEqual(first_data["simulated_time_utc"], second_data["simulated_time_utc"])

    def test_address_is_deterministic(self) -> None:
        token = self._auth(9090)
        first = self._get("/test/address", token)
        second = self._get("/test/address", token)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["data"]["address"], second.json()["data"]["address"])

    def test_deposit_and_withdraw_flow(self) -> None:
        token = self._auth()
        before_balance = self._get("/test/balance", token).json()["data"]["cash_usdt"]

        deposit_response = self._post("/test/deposit", {"amount": "250.00"}, token)
        self.assertEqual(deposit_response.status_code, 200)

        after_deposit = self._get("/test/balance", token).json()["data"]["cash_usdt"]
        self.assertGreater(after_deposit, before_balance)

        withdraw_response = self._post("/test/withdraw", {"amount": "50.00"}, token)
        self.assertEqual(withdraw_response.status_code, 200)

        insufficient_response = self._post("/test/withdraw", {"amount": "9999999"}, token)
        self.assertEqual(insufficient_response.status_code, 400)
        self.assertEqual(insufficient_response.json()["status"], "error")

    def test_wallet_amount_usdt_alias_supported(self) -> None:
        token = self._auth()

        deposit = self._post("/test/deposit", {"amount_usdt": "100.00"}, token)
        self.assertEqual(deposit.status_code, 200)

        withdraw = self._post("/test/withdraw", {"amount_usdt": "10.00"}, token)
        self.assertEqual(withdraw.status_code, 200)

        self._auth(2003)
        transfer = self._post(
            "/test/transfer",
            {"to_telegram_user_id": 2003, "amount_usdt": "5.00"},
            token,
        )
        self.assertEqual(transfer.status_code, 200)

    def test_deposit_upper_limit_enforced(self) -> None:
        token = self._auth()
        too_large = self._post("/test/deposit", {"amount": "1000000.01"}, token)
        self.assertEqual(too_large.status_code, 400)
        self.assertIn("test-mode limit", too_large.json()["message"])

    def test_transfer_between_users_and_self_transfer_error(self) -> None:
        sender_token = self._auth(2001)
        self._auth(2002)

        sender_before = Decimal(self._get("/test/balance", sender_token).json()["data"]["cash_usdt"])
        transfer_ok = self._post(
            "/test/transfer",
            {"to_telegram_user_id": 2002, "amount": "100.00"},
            sender_token,
        )
        self.assertEqual(transfer_ok.status_code, 200)

        sender_after = Decimal(self._get("/test/balance", sender_token).json()["data"]["cash_usdt"])
        self.assertLess(sender_after, sender_before)

        self_transfer = self._post(
            "/test/transfer",
            {"to_telegram_user_id": 2001, "amount": "10.00"},
            sender_token,
        )
        self.assertEqual(self_transfer.status_code, 400)

    def test_assets_and_asset_detail_include_marks_and_chart(self) -> None:
        token = self._auth()

        assets_response = self._get("/test/assets", token)
        self.assertEqual(assets_response.status_code, 200)
        assets = assets_response.json()["data"]["assets"]
        self.assertGreaterEqual(len(assets), 9)

        first_asset = assets[0]
        self.assertIn(first_asset["mark"], ["Buy", "Cover", "Sell", "Short", "Hold"])
        self.assertIn("pnl_percent", first_asset)
        self.assertIn("pnl_absolute", first_asset)

        detail_response = self._get(f"/test/asset/{first_asset['asset_id']}", token)
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()["data"]
        self.assertIn("balance", detail)
        self.assertIn("net_worth_chart", detail)
        self.assertGreater(len(detail["net_worth_chart"]), 0)
        self.assertIn("agent_marks", detail)

        bad_asset = self._get("/test/asset/INVALID", token)
        self.assertEqual(bad_asset.status_code, 404)

    def test_buy_sell_order_lifecycle_and_order_endpoints(self) -> None:
        token = self._auth()

        buy_response = self._post("/test/buy", {"asset_id": "AAPLx", "quantity": "2"}, token)
        self.assertEqual(buy_response.status_code, 200)
        buy_data = buy_response.json()["data"]
        self.assertEqual(buy_data["status"], "filled")
        order_id = buy_data["order_id"]

        order_response = self._get(f"/test/order/{order_id}", token)
        self.assertEqual(order_response.status_code, 200)
        self.assertEqual(order_response.json()["data"]["order_id"], order_id)

        orders_response = self._get("/test/orders", token)
        self.assertEqual(orders_response.status_code, 200)
        self.assertGreaterEqual(len(orders_response.json()["data"]["orders"]), 1)
        first_order = orders_response.json()["data"]["orders"][0]
        self.assertIn("realized_pnl", first_order)
        self.assertIn("realized_pnl_percent", first_order)

        sell_response = self._post("/test/sell", {"asset_id": "AAPLx", "quantity": "1"}, token)
        self.assertEqual(sell_response.status_code, 200)
        self.assertEqual(sell_response.json()["data"]["status"], "filled")

        invalid_sell = self._post("/test/sell", {"asset_id": "AAPLx", "quantity": "9999"}, token)
        self.assertEqual(invalid_sell.status_code, 400)

    def test_order_notional_and_price_are_stored_correctly(self) -> None:
        token = self._auth()

        prices = iter([Decimal("123.45"), Decimal("130.00")])

        def _price(asset_id: str) -> Decimal:
            if asset_id == "AAPLx":
                return next(prices)
            return TEST_PRICES.get(asset_id, Decimal("0"))

        with patch("wallet.services.prices.PricesService.get_price", side_effect=_price):
            buy = self._post("/test/buy", {"asset_id": "AAPLx", "quantity": "2"}, token)
            self.assertEqual(buy.status_code, 200)
            buy_data = buy.json()["data"]
            self.assertEqual(Decimal(buy_data["price"]), Decimal("123.45"))
            self.assertEqual(Decimal(buy_data["notional"]), Decimal("246.90"))

            sell = self._post("/test/sell", {"asset_id": "AAPLx", "quantity": "1"}, token)
            self.assertEqual(sell.status_code, 200)
            sell_data = sell.json()["data"]
            self.assertEqual(Decimal(sell_data["price"]), Decimal("130.00"))
            self.assertEqual(Decimal(sell_data["notional"]), Decimal("130.00"))

    def test_fifo_position_basis_after_multiple_buys_and_sell(self) -> None:
        token = self._auth()

        prices = [Decimal("100"), Decimal("200"), Decimal("300"), Decimal("250")]
        state = {"idx": 0}

        def _price(asset_id: str) -> Decimal:
            if asset_id == "AAPLx":
                idx = state["idx"]
                if idx < len(prices):
                    value = prices[idx]
                    state["idx"] = idx + 1
                    return value
                return prices[-1]
            return TEST_PRICES.get(asset_id, Decimal("0"))

        with patch("wallet.services.prices.PricesService.get_price", side_effect=_price):
            self.assertEqual(self._post("/test/buy", {"asset_id": "AAPLx", "quantity": "1"}, token).status_code, 200)
            self.assertEqual(self._post("/test/buy", {"asset_id": "AAPLx", "quantity": "1"}, token).status_code, 200)
            self.assertEqual(self._post("/test/sell", {"asset_id": "AAPLx", "quantity": "1"}, token).status_code, 200)

            positions = self._get("/test/positions", token).json()["data"]["positions"]
            aapl_position = next(p for p in positions if p["asset_id"] == "AAPLx")

            # FIFO leaves the second lot (entry 200) after selling one from [100, 200]
            self.assertEqual(Decimal(aapl_position["average_entry_price"]), Decimal("200.000000"))
            self.assertEqual(Decimal(aapl_position["quantity"]), Decimal("1.000000"))
            self.assertEqual(Decimal(aapl_position["pnl_absolute"]), Decimal("50.00"))
            self.assertEqual(Decimal(aapl_position["pnl_percent"]), Decimal("25.00"))

    def test_pnl_uses_current_market_prices(self) -> None:
        token = self._auth()
        self._post("/test/buy", {"asset_id": "AAPLx", "quantity": "1"}, token)

        def _price_side_effect(asset_id: str) -> Decimal:
            if asset_id == "AAPLx":
                return Decimal("250.00")
            return TEST_PRICES.get(asset_id, Decimal("0"))

        with patch("wallet.services.prices.PricesService.get_price", side_effect=_price_side_effect):
            positions = self._get("/test/positions", token).json()["data"]["positions"]
            aapl_position = next(p for p in positions if p["asset_id"] == "AAPLx")
            self.assertGreater(Decimal(aapl_position["pnl_absolute"]), Decimal("0"))
            self.assertGreater(Decimal(aapl_position["pnl_percent"]), Decimal("0"))

            balance = self._get("/test/balance", token).json()["data"]
            self.assertGreater(Decimal(balance["pnl_absolute"]), Decimal("0"))

    def test_buy_sell_accept_case_insensitive_asset_ids(self) -> None:
        token = self._auth()

        buy_lower = self._post("/test/buy", {"asset_id": "aaplx", "quantity": "1"}, token)
        self.assertEqual(buy_lower.status_code, 200)
        self.assertEqual(buy_lower.json()["data"]["asset_id"], "AAPLx")

        sell_mixed = self._post("/test/sell", {"asset_id": "AaPlX", "quantity": "0.5"}, token)
        self.assertEqual(sell_mixed.status_code, 200)
        self.assertEqual(sell_mixed.json()["data"]["asset_id"], "AAPLx")

    def test_buy_sell_support_amount_usdt_payload(self) -> None:
        token = self._auth()
        before_cash = Decimal(self._get("/test/balance", token).json()["data"]["cash_usdt"])

        buy = self._post("/test/buy", {"asset_id": "aaplx", "amount_usdt": "500"}, token)
        self.assertEqual(buy.status_code, 200)
        self.assertEqual(Decimal(buy.json()["data"]["notional"]), Decimal("500.00"))
        self.assertGreater(Decimal(buy.json()["data"]["quantity"]), Decimal("0"))
        after_buy_cash = Decimal(self._get("/test/balance", token).json()["data"]["cash_usdt"])
        self.assertEqual(after_buy_cash, before_cash - Decimal("500.00"))

        sell = self._post("/test/sell", {"asset_id": "AAPLx", "amount_usdt": "100"}, token)
        self.assertEqual(sell.status_code, 200)
        self.assertEqual(Decimal(sell.json()["data"]["notional"]), Decimal("100.00"))
        self.assertGreater(Decimal(sell.json()["data"]["quantity"]), Decimal("0"))
        after_sell_cash = Decimal(self._get("/test/balance", token).json()["data"]["cash_usdt"])
        self.assertEqual(after_sell_cash, after_buy_cash + Decimal("100.00"))

    def test_balance_read_does_not_mutate_cash(self) -> None:
        token = self._auth()
        before = Decimal(self._get("/test/balance", token).json()["data"]["cash_usdt"])
        self._get("/test/balance", token)
        after = Decimal(self._get("/test/balance", token).json()["data"]["cash_usdt"])
        self.assertEqual(before, after)

    def test_positions_include_marks(self) -> None:
        token = self._auth()
        self._post("/test/buy", {"asset_id": "TSLAx", "quantity": "1"}, token)

        positions_response = self._get("/test/positions", token)
        self.assertEqual(positions_response.status_code, 200)

        positions = positions_response.json()["data"]["positions"]
        self.assertGreaterEqual(len(positions), 1)
        self.assertIn(positions[0]["mark"], ["Buy", "Cover", "Sell", "Short", "Hold"])

    def test_agents_endpoints(self) -> None:
        token = self._auth()

        agents_response = self._get("/test/agents", token)
        self.assertEqual(agents_response.status_code, 200)
        agents_data = agents_response.json()["data"]
        self.assertEqual(agents_data["active_agents"], agents_data["selected_agents"])
        self.assertLessEqual(len(agents_data["active_agents"]), 3)
        self.assertGreaterEqual(len(agents_data["selected_agents"]), 1)

        select_response = self._post(
            "/test/agents/select",
            {"selected_agents": ["warren_buffett", "pavel_durov"]},
            token,
        )
        self.assertEqual(select_response.status_code, 200)

        allocation_response = self._get("/test/agents/allocation", token)
        self.assertEqual(allocation_response.status_code, 200)
        allocation = allocation_response.json()["data"]["allocation"]
        self.assertAlmostEqual(sum(allocation.values()), 100.0)

        allocation_update = self._post(
            "/test/agents/allocation",
            {
                "allocation": {
                    "warren_buffett": 60.0,
                    "pavel_durov": 40.0,
                }
            },
            token,
        )
        self.assertEqual(allocation_update.status_code, 200)

        with patch("wallet.views.agents.AIAgentsService.get_reasoning") as mock_reasoning:
            mock_reasoning.return_value.asset_id = "AAPLx"
            mock_reasoning.return_value.reasoning = ["Mock agent reasoning", "Second mock reason"]
            mock_reasoning.return_value.recommendation = "warren_buffett"

            reasoning_response = self._get("/test/agents/reasoning?asset_id=AAPLx", token)
            self.assertEqual(reasoning_response.status_code, 200)
            self.assertGreaterEqual(len(reasoning_response.json()["data"]["reasoning"]), 1)

    def test_test_agents_prefers_configure_team_when_legacy_selection_stale(self) -> None:
        token = self._auth()

        configured = self._post(
            "/advisors/preferences",
            {
                "selected_advisors": ["warren_buffett", "pavel_durov", "ray_dalio"],
                "advisor_weights": {
                    "warren_buffett": 40.0,
                    "pavel_durov": 35.0,
                    "ray_dalio": 25.0,
                },
                "risk_profile": "medium",
            },
            token,
        )
        self.assertEqual(configured.status_code, 200)

        # Simulate stale legacy rows from old schema usage.
        preference = AgentPreference.objects.get(account__identity__token=token)
        preference.selected_agents = ["Buy", "Cover", "Hold"]
        preference.allocation = {"Buy": 33.34, "Cover": 33.33, "Hold": 33.33}
        preference.save(update_fields=["selected_agents", "allocation", "updated_at"])

        agents_response = self._get("/test/agents", token)
        self.assertEqual(agents_response.status_code, 200)
        agents_data = agents_response.json()["data"]
        self.assertEqual(
            agents_data["selected_agents"],
            ["warren_buffett", "pavel_durov", "ray_dalio"],
        )
        self.assertEqual(
            agents_data["allocation"],
            {"warren_buffett": 40.0, "pavel_durov": 35.0, "ray_dalio": 25.0},
        )
        self.assertEqual(agents_data["active_agents"], agents_data["selected_agents"])

    def test_test_agents_select_rejects_legacy_agent_ids(self) -> None:
        token = self._auth()
        response = self._post(
            "/test/agents/select",
            {"selected_agents": ["Buy", "Hold"]},
            token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid agent IDs", response.json()["message"])

    def test_test_agents_ignores_legacy_selected_advisors_values(self) -> None:
        token = self._auth()

        configured = self._post(
            "/advisors/preferences",
            {
                "selected_advisors": ["warren_buffett", "pavel_durov", "ray_dalio"],
                "advisor_weights": {
                    "warren_buffett": 60.0,
                    "pavel_durov": 30.0,
                    "ray_dalio": 10.0,
                },
                "risk_profile": "medium",
            },
            token,
        )
        self.assertEqual(configured.status_code, 200)

        # Simulate a corrupted row where selected_advisors keeps legacy values.
        preference = AgentPreference.objects.get(account__identity__token=token)
        preference.selected_advisors = ["Buy", "Cover", "Sell", "Short", "Hold"]
        preference.advisor_weights = {
            "Buy": 20.0,
            "Cover": 20.0,
            "Sell": 20.0,
            "Short": 20.0,
            "Hold": 20.0,
        }
        preference.save(update_fields=["selected_advisors", "advisor_weights", "updated_at"])

        agents_response = self._get("/test/agents", token)
        self.assertEqual(agents_response.status_code, 200)
        agents_data = agents_response.json()["data"]
        self.assertEqual(
            agents_data["selected_agents"],
            ["warren_buffett", "pavel_durov", "ray_dalio"],
        )
        self.assertEqual(
            agents_data["allocation"],
            {"warren_buffett": 60.0, "pavel_durov": 30.0, "ray_dalio": 10.0},
        )
        self.assertEqual(agents_data["active_agents"], agents_data["selected_agents"])

    def test_portfolio_risk_and_rebalance(self) -> None:
        token = self._auth()
        self._post("/test/buy", {"asset_id": "NVDAx", "quantity": "1"}, token)

        portfolio_response = self._get("/test/portfolio", token)
        self.assertEqual(portfolio_response.status_code, 200)
        portfolio = portfolio_response.json()["data"]
        self.assertIn("total_balance_usdt", portfolio)
        self.assertIn("pnl_percent", portfolio)
        self.assertIn("pnl_absolute", portfolio)
        self.assertIn("allocation", portfolio)

        risk_response = self._get("/test/risk", token)
        self.assertEqual(risk_response.status_code, 200)
        self.assertIn("risk_score", risk_response.json()["data"])

        rebalance_response = self._post("/test/rebalance", {}, token)
        self.assertEqual(rebalance_response.status_code, 200)
        self.assertIn("actions", rebalance_response.json()["data"])
