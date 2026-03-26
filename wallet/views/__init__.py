"""Wallet views package - exports all view classes."""
from __future__ import annotations

from .auth import (
    TelegramAuthView,
    TelegramLoginWidgetView,
    PendingAuthView,
    CompleteAuthView,
    SessionValidateView,
    HealthView,
    WebSocketView,
)
from .bot import BotInfoView
from .wallet import (
    TestAddressView,
    TestBalanceView,
    TestDepositView,
    TestTimeView,
    TestTransferView,
    TestWithdrawView,
)
from .trading import (
    TestAssetDetailView,
    TestAssetsView,
    TestBuyView,
    TestOrderView,
    TestOrdersView,
    TestPositionsView,
    TestPricesView,
    TestSellView,
)
from .agents import (
    AgentsActiveView,
    TestAgentsAllocationView,
    TestAgentsReasoningView,
    TestAgentsSelectView,
    TestAgentsView,
)
from .advisors import (
    AdvisorAssetAnalysisView,
    AdvisorOnboardingResetView,
    AdvisorsListView,
    AdvisorPortfolioRecommendationsView,
    AdvisorPreferencesView,
    AdvisorStartView,
)
from .portfolio import (
    TestPortfolioView,
    TestRebalanceView,
    TestRiskView,
)

__all__ = [
    # Auth
    "TelegramAuthView",
    "TelegramLoginWidgetView",
    "PendingAuthView",
    "CompleteAuthView",
    "SessionValidateView",
    "HealthView",
    "WebSocketView",
    # Bot
    "BotInfoView",
    # Wallet
    "TestBalanceView",
    "TestAddressView",
    "TestTimeView",
    "TestDepositView",
    "TestWithdrawView",
    "TestTransferView",
    # Trading
    "TestAssetsView",
    "TestAssetDetailView",
    "TestPositionsView",
    "TestBuyView",
    "TestSellView",
    "TestOrderView",
    "TestOrdersView",
    "TestPricesView",
    # Agents
    "TestAgentsView",
    "AgentsActiveView",
    "TestAgentsSelectView",
    "TestAgentsAllocationView",
    "TestAgentsReasoningView",
    "AdvisorsListView",
    "AdvisorAssetAnalysisView",
    "AdvisorOnboardingResetView",
    "AdvisorPreferencesView",
    "AdvisorStartView",
    "AdvisorPortfolioRecommendationsView",
    # Portfolio
    "TestPortfolioView",
    "TestRebalanceView",
    "TestRiskView",
]
