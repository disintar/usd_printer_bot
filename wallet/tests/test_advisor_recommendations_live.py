from __future__ import annotations

import os
import time
import unittest
from decimal import Decimal
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.conf import settings
from django.test import TestCase

from wallet.models import AgentPreference, AssetPosition, TelegramIdentity, WalletAccount
from wallet.services.advisor_recommendations import AdvisorRecommendationsService
from wallet.services.financial_mcp import FinancialMcpService
from wallet.services.llm_advice import LlmAdviceService


class AdvisorRecommendationsLiveTests(TestCase):
    """Live integration tests for real MCP + LLM advisor calls."""

    LIVE_MAX_SECONDS = 60.0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if os.getenv("RUN_LIVE_ADVISOR_TESTS", "false").lower() != "true":
            raise unittest.SkipTest("RUN_LIVE_ADVISOR_TESTS is not true")
        if not getattr(settings, "MCP_ENABLED", False):
            raise unittest.SkipTest("MCP_ENABLED is false")
        if not str(getattr(settings, "MCP_SERVER_URL", "")).strip():
            raise unittest.SkipTest("MCP_SERVER_URL is empty")
        if not str(getattr(settings, "OPENAI_API_KEY", "")).strip():
            raise unittest.SkipTest("OPENAI_API_KEY is empty")
        if not str(getattr(settings, "OPENAI_BASE_URL", "")).strip():
            raise unittest.SkipTest("OPENAI_BASE_URL is empty")

    def setUp(self) -> None:
        self.identity = TelegramIdentity.objects.create(
            telegram_user_id=700001,
            username="live_advisor",
            token="live_advisor_token",
        )
        self.account = WalletAccount.objects.create(
            identity=self.identity,
            cash_balance=Decimal("10000.00"),
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

    def _set_risk(self, risk_profile: str) -> None:
        preference = self.account.agent_preference
        preference.risk_profile = risk_profile
        preference.save(update_fields=["risk_profile", "updated_at"])

    def _set_portfolio_mix(self, cash: str, positions: list[tuple[str, str, str]]) -> None:
        self.account.cash_balance = Decimal(cash)
        self.account.save(update_fields=["cash_balance", "updated_at"])
        AssetPosition.objects.filter(account=self.account).delete()
        for asset_id, qty, entry in positions:
            AssetPosition.objects.create(
                account=self.account,
                asset_id=asset_id,
                quantity=Decimal(qty),
                average_entry_price=Decimal(entry),
            )

    def _timed_call(self, fn):
        started = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - started
        self.assertLess(
            elapsed,
            self.LIVE_MAX_SECONDS,
            f"Call was too slow: {elapsed:.2f}s (limit {self.LIVE_MAX_SECONDS:.2f}s)",
        )
        return result, elapsed

    def test_live_start_recommendations_speed_by_risk(self) -> None:
        durations: list[float] = []
        for risk in ["low", "medium", "high"]:
            self._set_risk(risk)
            with (
                patch.object(
                    FinancialMcpService,
                    "list_market_snapshots",
                    wraps=FinancialMcpService.list_market_snapshots,
                ) as mcp_call,
                patch.object(
                    LlmAdviceService,
                    "complete_tool_input",
                    wraps=LlmAdviceService.complete_tool_input,
                ) as llm_call,
            ):
                result, elapsed = self._timed_call(
                    lambda: async_to_sync(AdvisorRecommendationsService.get_start_recommendations)(
                        self.account,
                        Decimal("1000.00"),
                    )
                )
                self.assertGreaterEqual(mcp_call.call_count, 1)
                self.assertGreaterEqual(llm_call.call_count, 1)
            durations.append(elapsed)
            recommendations = result["buy_recommendations"]
            self.assertGreaterEqual(len(recommendations), 1)
            self.assertLessEqual(len(recommendations), 3)
            total = sum(Decimal(item["allocation_percent"]) for item in recommendations)
            self.assertEqual(total, Decimal("100.00"))
            print(f"[live-start] risk={risk} elapsed={elapsed:.2f}s recommendations={len(recommendations)}")
        self.assertGreaterEqual(len(durations), 3)

    def test_live_portfolio_recommendations_speed_by_allocation_and_risk(self) -> None:
        scenarios = [
            ("low", "9000.00", [("AAPLx", "2.0", "180.00"), ("TSLAx", "1.0", "210.00")]),
            ("medium", "6000.00", [("AAPLx", "5.0", "180.00"), ("NVDAx", "1.0", "780.00")]),
            ("high", "2500.00", [("TSLAx", "6.0", "200.00"), ("MSTRx", "0.5", "1100.00")]),
        ]
        for risk, cash, positions in scenarios:
            self._set_risk(risk)
            self._set_portfolio_mix(cash, positions)
            with (
                patch.object(
                    FinancialMcpService,
                    "list_market_snapshots",
                    wraps=FinancialMcpService.list_market_snapshots,
                ) as mcp_call,
                patch.object(
                    LlmAdviceService,
                    "complete_tool_input",
                    wraps=LlmAdviceService.complete_tool_input,
                ) as llm_call,
            ):
                result, elapsed = self._timed_call(
                    lambda: async_to_sync(AdvisorRecommendationsService.get_portfolio_recommendations)(
                        self.account
                    )
                )
                self.assertGreaterEqual(mcp_call.call_count, 1)
                self.assertGreaterEqual(llm_call.call_count, 1)
            actions = result["actions"]
            self.assertIsInstance(actions, list)
            print(f"[live-portfolio] risk={risk} cash={cash} elapsed={elapsed:.2f}s actions={len(actions)}")

    def test_live_asset_analysis_speed_by_ticker_and_risk(self) -> None:
        tickers = ["AAPLx", "TSLAx", "NVDAx"]
        for risk in ["low", "high"]:
            self._set_risk(risk)
            for ticker in tickers:
                with (
                    patch.object(
                        FinancialMcpService,
                        "list_market_snapshots",
                        wraps=FinancialMcpService.list_market_snapshots,
                    ) as mcp_call,
                    patch.object(
                        LlmAdviceService,
                        "complete_json",
                        wraps=LlmAdviceService.complete_json,
                    ) as llm_call,
                ):
                    result, elapsed = self._timed_call(
                        lambda: async_to_sync(AdvisorRecommendationsService.get_asset_analysis)(
                            self.account,
                            ticker,
                        )
                    )
                    self.assertGreaterEqual(mcp_call.call_count, 1)
                    self.assertGreaterEqual(llm_call.call_count, 1)
                self.assertEqual(result["asset_id"], ticker)
                self.assertIn(result["recommendation"], {"buy", "hold", "sell"})
                notes = result["advisor_notes"]
                self.assertIsInstance(notes, list)
                self.assertGreaterEqual(len(notes), 1)
                print(
                    f"[live-asset] risk={risk} ticker={ticker} elapsed={elapsed:.2f}s "
                    f"fallback={str(result['summary']).startswith('Fallback analytics mode:')}"
                )
