from __future__ import annotations

import time
from decimal import Decimal
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TestCase

from wallet.constants import TRADEABLE_ASSET_IDS
from wallet.models import AgentPreference, AssetPosition, TelegramIdentity, WalletAccount
from wallet.services.advisor_recommendations import AdvisorRecommendationsService
from wallet.services.financial_mcp import FinancialMcpError, MarketSnapshot


class AdvisorRecommendationsServiceTests(TestCase):
    def setUp(self) -> None:
        self.identity = TelegramIdentity.objects.create(
            telegram_user_id=500001,
            username="perf_user",
            token="token_perf_user",
        )
        self.account = WalletAccount.objects.create(
            identity=self.identity,
            cash_balance=Decimal("8000.00"),
            initial_cash=Decimal("10000.00"),
            net_cash_flow=Decimal("0.00"),
        )
        AgentPreference.objects.create(
            account=self.account,
            selected_agents=AgentPreference.default_selected_agents(),
            allocation=AgentPreference.default_allocation(),
            selected_advisors=["warren_buffett", "pavel_durov"],
            risk_profile="medium",
        )
        AssetPosition.objects.create(
            account=self.account,
            asset_id="AAPLx",
            quantity=Decimal("5.000000"),
            average_entry_price=Decimal("180.000000"),
        )
        AssetPosition.objects.create(
            account=self.account,
            asset_id="TSLAx",
            quantity=Decimal("3.000000"),
            average_entry_price=Decimal("200.000000"),
        )

    @staticmethod
    def _snapshots() -> list[MarketSnapshot]:
        return [
            MarketSnapshot(
                asset_id="AAPLx",
                symbol="AAPL",
                price=Decimal("190"),
                target_consensus=Decimal("210"),
                target_high=Decimal("230"),
                target_low=Decimal("170"),
            ),
            MarketSnapshot(
                asset_id="TSLAx",
                symbol="TSLA",
                price=Decimal("220"),
                target_consensus=Decimal("205"),
                target_high=Decimal("260"),
                target_low=Decimal("180"),
            ),
        ]

    @patch("wallet.services.advisor_recommendations.LlmAdviceService.complete_tool_input")
    @patch("wallet.services.advisor_recommendations.FinancialMcpService.list_market_snapshots")
    def test_get_start_recommendations_returns_new_notebook_shape(
        self,
        mock_snapshots,
        mock_llm,
    ) -> None:
        mock_snapshots.return_value = self._snapshots()
        mock_llm.return_value = {
            "buy_recommendations": [
                {
                    "asset_id": "AAPLx",
                    "allocation_percent": "60.00",
                    "verdict": "buy",
                    "reason": "Strong upside.",
                },
                {
                    "asset_id": "TSLAx",
                    "allocation_percent": "40.00",
                    "verdict": "hold",
                    "reason": "Keep some optionality.",
                },
            ],
            "advisor_summaries": [
                {"advisor_id": "warren_buffett", "summary": "Prefers quality and margin of safety."},
                {"advisor_id": "pavel_durov", "summary": "Wants product-led growth exposure."},
            ],
        }

        started = time.perf_counter()
        result = async_to_sync(AdvisorRecommendationsService.get_start_recommendations)(
            self.account,
            Decimal("1000.00"),
        )
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.10)
        self.assertEqual(len(result["buy_recommendations"]), 2)
        self.assertEqual(
            sum(Decimal(item["allocation_percent"]) for item in result["buy_recommendations"]),
            Decimal("100.00"),
        )
        self.assertEqual(result["advisor_summaries"][0]["advisor_id"], "warren_buffett")
        self.account.agent_preference.refresh_from_db()
        self.assertEqual(
            self.account.agent_preference.initial_portfolio["buy_recommendations"][0]["asset_id"],
            "AAPLx",
        )

    @patch("wallet.services.advisor_recommendations.LlmAdviceService.complete_tool_input")
    @patch("wallet.services.advisor_recommendations.FinancialMcpService.list_market_snapshots")
    def test_get_start_recommendations_normalizes_allocation_percent_formats(
        self,
        mock_snapshots,
        mock_llm,
    ) -> None:
        mock_snapshots.return_value = self._snapshots()
        mock_llm.return_value = {
            "buy_recommendations": [
                {
                    "asset_id": "AAPLx",
                    "allocation_percent": "60%",
                    "verdict": "buy",
                    "reason": "Strong upside.",
                },
                {
                    "asset_id": "TSLAx",
                    "allocation_percent": "40,00",
                    "verdict": "hold",
                    "reason": "Keep optionality.",
                },
            ],
            "advisor_summaries": [
                {"advisor_id": "warren_buffett", "summary": "Prefers quality and margin of safety."},
                {"advisor_id": "pavel_durov", "summary": "Wants product-led growth exposure."},
            ],
        }

        result = async_to_sync(AdvisorRecommendationsService.get_start_recommendations)(
            self.account,
            Decimal("1000.00"),
        )
        self.assertEqual(result["buy_recommendations"][0]["allocation_percent"], "60.00")
        self.assertEqual(result["buy_recommendations"][1]["allocation_percent"], "40.00")

    @patch("wallet.services.advisor_recommendations.LlmAdviceService.complete_tool_input")
    @patch("wallet.services.advisor_recommendations.FinancialMcpService.list_market_snapshots")
    @patch("wallet.services.advisor_recommendations.AdvisorsService.list_advisors")
    def test_get_start_recommendations_maps_advisor_name_in_summaries(
        self,
        mock_list_advisors,
        mock_snapshots,
        mock_llm,
    ) -> None:
        from wallet.services.advisors import AdvisorDefinition

        mock_list_advisors.return_value = [
            AdvisorDefinition(
                advisor_id="warren_buffett",
                name="Warren Buffett",
                category="serious",
                role="Long-term value investor",
                style=["value"],
                tags=["value"],
                primary_tag="investments",
                tabler_icon="IconMoodSmile",
            ),
            AdvisorDefinition(
                advisor_id="pavel_durov",
                name="Pavel Durov",
                category="playful",
                role="Founder-operator",
                style=["direct"],
                tags=["product"],
                primary_tag="business",
                tabler_icon="IconMoodNerd",
            ),
        ]
        mock_snapshots.return_value = self._snapshots()
        mock_llm.return_value = {
            "buy_recommendations": [
                {
                    "asset_id": "AAPLx",
                    "allocation_percent": "60.00",
                    "verdict": "buy",
                    "reason": "Strong upside.",
                },
                {
                    "asset_id": "TSLAx",
                    "allocation_percent": "40.00",
                    "verdict": "hold",
                    "reason": "Keep optionality.",
                },
            ],
            "advisor_summaries": [
                {"advisor_id": "Warren Buffett", "summary": "I want durable earnings at sensible risk."},
                {"advisor_id": "Pavel Durov", "summary": "Ship fast, keep control, and concentrate upside."},
            ],
        }

        result = async_to_sync(AdvisorRecommendationsService.get_start_recommendations)(
            self.account,
            Decimal("1000.00"),
        )
        self.assertEqual(result["advisor_summaries"][0]["advisor_id"], "warren_buffett")
        self.assertEqual(result["advisor_summaries"][1]["advisor_id"], "pavel_durov")

    @patch("wallet.services.advisor_recommendations.LlmAdviceService.complete_tool_input")
    @patch("wallet.services.advisor_recommendations.FinancialMcpService.list_market_snapshots")
    def test_get_saved_start_recommendations_returns_persisted_portfolio(
        self,
        mock_snapshots,
        mock_llm,
    ) -> None:
        mock_snapshots.return_value = self._snapshots()
        mock_llm.return_value = {
            "buy_recommendations": [
                {
                    "asset_id": "AAPLx",
                    "allocation_percent": "100.00",
                    "verdict": "buy",
                    "reason": "Persist me.",
                }
            ],
            "advisor_summaries": [
                {"advisor_id": "warren_buffett", "summary": "Saved advisor summary."},
            ],
        }
        async_to_sync(AdvisorRecommendationsService.get_start_recommendations)(
            self.account,
            Decimal("900.00"),
        )

        saved = async_to_sync(AdvisorRecommendationsService.get_saved_start_recommendations)(self.account)
        self.assertIsNotNone(saved)
        if saved is None:
            self.fail("Expected saved initial portfolio")
        self.assertEqual(saved["buy_recommendations"][0]["asset_id"], "AAPLx")
        self.assertEqual(saved["advisor_summaries"][0]["advisor_id"], "warren_buffett")

    @patch("wallet.services.advisor_recommendations.LlmAdviceService.complete_tool_input")
    @patch("wallet.services.advisor_recommendations.FinancialMcpService.list_market_snapshots")
    def test_get_portfolio_recommendations_returns_actions_array(
        self,
        mock_snapshots,
        mock_llm,
    ) -> None:
        mock_snapshots.return_value = self._snapshots()
        mock_llm.return_value = {
            "actions": [
                {
                    "asset_id": "AAPLx",
                    "action": "hold",
                    "reason": "Quality core holding.",
                },
                {
                    "asset_id": "NVDAx",
                    "action": "buy",
                    "reason": "Best new use of available cash.",
                },
            ]
        }

        for risk_profile in ["low", "medium", "high"]:
            pref = self.account.agent_preference
            pref.risk_profile = risk_profile
            pref.save(update_fields=["risk_profile", "updated_at"])

            started = time.perf_counter()
            result = async_to_sync(AdvisorRecommendationsService.get_portfolio_recommendations)(
                self.account
            )
            elapsed = time.perf_counter() - started

            self.assertLess(elapsed, 0.12)
            self.assertEqual(len(result["actions"]), len(TRADEABLE_ASSET_IDS))
            actions_by_asset_id = {
                item["asset_id"]: item["action"] for item in result["actions"]
            }
            self.assertEqual(actions_by_asset_id["AAPLx"], "hold")
            self.assertEqual(actions_by_asset_id["NVDAx"], "buy")

    @patch("wallet.services.advisor_recommendations.LlmAdviceService.complete_tool_input")
    @patch("wallet.services.advisor_recommendations.FinancialMcpService.list_market_snapshots")
    def test_get_portfolio_recommendations_fills_missing_assets_with_hold(
        self,
        mock_snapshots,
        mock_llm,
    ) -> None:
        mock_snapshots.return_value = self._snapshots()
        mock_llm.return_value = {
            "actions": [
                {
                    "asset_id": "AAPLx",
                    "action": "sell",
                    "reason": "Trim after downside revision.",
                }
            ]
        }

        result = async_to_sync(AdvisorRecommendationsService.get_portfolio_recommendations)(
            self.account
        )

        self.assertEqual(len(result["actions"]), len(TRADEABLE_ASSET_IDS))
        actions_by_asset_id = {
            item["asset_id"]: item for item in result["actions"]
        }
        self.assertEqual(actions_by_asset_id["AAPLx"]["action"], "sell")
        self.assertEqual(actions_by_asset_id["TSLAx"]["action"], "hold")
        self.assertEqual(
            actions_by_asset_id["TSLAx"]["reason"],
            "No strong change signal right now.",
        )

    @patch("wallet.services.advisor_recommendations.LlmAdviceService.complete_tool_input")
    @patch("wallet.services.advisor_recommendations.FinancialMcpService.list_market_snapshots")
    def test_get_asset_analysis_speed_for_different_tickers(
        self,
        mock_snapshots,
        mock_llm,
    ) -> None:
        def snapshots_side_effect(asset_ids: list[str]) -> list[MarketSnapshot]:
            asset_id = asset_ids[0]
            return [
                MarketSnapshot(
                    asset_id=asset_id,
                    symbol=asset_id.replace("x", ""),
                    price=Decimal("200"),
                    target_consensus=Decimal("215"),
                    target_high=Decimal("230"),
                    target_low=Decimal("185"),
                )
            ]

        mock_snapshots.side_effect = snapshots_side_effect
        mock_llm.return_value = {
            "recommendation": "buy",
            "summary": "Single-asset analysis.",
            "advisor_notes": [
                {"advisor_id": "warren_buffett", "thought": "Durable business."},
                {"advisor_id": "pavel_durov", "thought": "Product velocity is good."},
            ],
        }

        for ticker in ["AAPLx", "TSLAx", "NVDAx"]:
            started = time.perf_counter()
            result = async_to_sync(AdvisorRecommendationsService.get_asset_analysis)(
                self.account,
                ticker,
            )
            elapsed = time.perf_counter() - started
            self.assertLess(elapsed, 0.12)
            self.assertEqual(result["asset_id"], ticker)
            self.assertEqual(result["recommendation"], "buy")
            self.assertEqual(len(result["advisor_notes"]), 2)

    @patch(
        "wallet.services.advisor_recommendations.FinancialMcpService.list_market_snapshots",
        side_effect=FinancialMcpError("MCP disabled"),
    )
    def test_get_portfolio_recommendations_raises_without_fallback(self, mock_snapshots) -> None:
        with self.assertRaises(FinancialMcpError):
            async_to_sync(AdvisorRecommendationsService.get_portfolio_recommendations)(self.account)

    @patch(
        "wallet.services.advisor_recommendations.FinancialMcpService.list_market_snapshots",
        side_effect=FinancialMcpError("MCP disabled"),
    )
    def test_get_start_recommendations_raises_without_fallback(self, mock_snapshots) -> None:
        with self.assertRaises(FinancialMcpError):
            async_to_sync(AdvisorRecommendationsService.get_start_recommendations)(
                self.account,
                Decimal("1200.00"),
            )

    @patch("wallet.services.advisor_recommendations.LlmAdviceService.complete_tool_input")
    @patch("wallet.services.advisor_recommendations.FinancialMcpService.list_market_snapshots")
    def test_get_portfolio_recommendations_scrapes_mcp_before_single_llm_call(
        self,
        mock_snapshots,
        mock_llm,
    ) -> None:
        events: list[str] = []

        def snapshots_side_effect(asset_ids: list[str]) -> list[MarketSnapshot]:
            events.append("mcp")
            self.assertEqual(asset_ids, list(TRADEABLE_ASSET_IDS))
            return self._snapshots()

        def llm_side_effect(**kwargs) -> dict[str, object]:
            events.append("llm")
            self.assertEqual(kwargs["tool_name"], "emit_portfolio_actions")
            self.assertTrue(kwargs["system_prompt"])
            self.assertTrue(kwargs["user_prompt"])
            return {
                "actions": [
                    {
                        "asset_id": "AAPLx",
                        "action": "hold",
                        "reason": "Quality core position.",
                    }
                ]
            }

        mock_snapshots.side_effect = snapshots_side_effect
        mock_llm.side_effect = llm_side_effect

        result = async_to_sync(AdvisorRecommendationsService.get_portfolio_recommendations)(
            self.account
        )

        self.assertEqual(events, ["mcp", "llm"])
        self.assertEqual(mock_snapshots.call_count, 1)
        self.assertEqual(mock_llm.call_count, 1)
        self.assertEqual(len(result["actions"]), len(TRADEABLE_ASSET_IDS))
        actions_by_asset_id = {
            item["asset_id"]: item["action"] for item in result["actions"]
        }
        self.assertEqual(actions_by_asset_id["AAPLx"], "hold")
