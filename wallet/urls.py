"""URL configuration for wallet API."""
from __future__ import annotations

from django.urls import path

from .views import (
    AdvisorsListView,
    AdvisorAssetAnalysisView,
    AdvisorOnboardingResetView,
    AdvisorPortfolioRecommendationsView,
    AdvisorPreferencesView,
    AdvisorStartView,
    # Auth
    TelegramAuthView,
    TelegramLoginWidgetView,
    PendingAuthView,
    CompleteAuthView,
    SessionValidateView,
    HealthView,
    WebSocketView,
    # Bot
    BotInfoView,
    # Wallet
    TestBalanceView,
    TestAddressView,
    TestTimeView,
    TestDepositView,
    TestWithdrawView,
    TestTransferView,
    # Trading
    TestAssetsView,
    TestAssetDetailView,
    TestPositionsView,
    TestBuyView,
    TestSellView,
    TestOrderView,
    TestOrdersView,
    TestPricesView,
    # Agents
    TestAgentsView,
    TestAgentsSelectView,
    TestAgentsAllocationView,
    TestAgentsReasoningView,
    AgentsActiveView,
    # Portfolio
    TestPortfolioView,
    TestRebalanceView,
    TestRiskView,
)

app_name = "wallet"

urlpatterns = [
    # Health and WebSocket
    path("health", HealthView.as_view(), name="health"),
    path("ws", WebSocketView.as_view(), name="ws"),

    # Bot info
    path("bot/info", BotInfoView.as_view(), name="bot_info"),

    # Authentication
    path("auth/telegram", TelegramAuthView.as_view(), name="auth_telegram"),
    path("auth/telegram/widget", TelegramLoginWidgetView.as_view(), name="auth_telegram_widget"),
    path("auth/pending", PendingAuthView.as_view(), name="auth_pending"),
    path("auth/pending/<str:token>", PendingAuthView.as_view(), name="auth_pending_check"),
    path("auth/complete", CompleteAuthView.as_view(), name="auth_complete"),
    path("auth/session/<str:token>", SessionValidateView.as_view(), name="auth_session"),

    # Wallet
    path("test/balance", TestBalanceView.as_view(), name="test_balance"),
    path("test/address", TestAddressView.as_view(), name="test_address"),
    path("test/time", TestTimeView.as_view(), name="test_time"),
    path("test/deposit", TestDepositView.as_view(), name="test_deposit"),
    path("test/withdraw", TestWithdrawView.as_view(), name="test_withdraw"),
    path("test/transfer", TestTransferView.as_view(), name="test_transfer"),

    # Trading
    path("test/assets", TestAssetsView.as_view(), name="test_assets"),
    path("test/asset/<str:asset_id>", TestAssetDetailView.as_view(), name="test_asset_detail"),
    path("test/positions", TestPositionsView.as_view(), name="test_positions"),
    path("test/buy", TestBuyView.as_view(), name="test_buy"),
    path("test/sell", TestSellView.as_view(), name="test_sell"),
    path("test/order/<int:order_id>", TestOrderView.as_view(), name="test_order"),
    path("test/orders", TestOrdersView.as_view(), name="test_orders"),
    path("test/prices", TestPricesView.as_view(), name="test_prices"),

    # Agents
    path("advisors/list", AdvisorsListView.as_view(), name="advisors_list"),
    path("advisors/preferences", AdvisorPreferencesView.as_view(), name="advisor_preferences"),
    path(
        "advisors/onboarding/reset",
        AdvisorOnboardingResetView.as_view(),
        name="advisor_onboarding_reset",
    ),
    path("advisors/start", AdvisorStartView.as_view(), name="advisor_start"),
    path("advisors/analysis", AdvisorAssetAnalysisView.as_view(), name="advisor_analysis"),
    path(
        "advisors/recommendations",
        AdvisorPortfolioRecommendationsView.as_view(),
        name="advisor_recommendations",
    ),
    path("test/agents", TestAgentsView.as_view(), name="test_agents"),
    path("test/agents/select", TestAgentsSelectView.as_view(), name="test_agents_select"),
    path("test/agents/allocation", TestAgentsAllocationView.as_view(), name="test_agents_allocation"),
    path("test/agents/reasoning", TestAgentsReasoningView.as_view(), name="test_agents_reasoning"),
    path("agents/active", AgentsActiveView.as_view(), name="agents_active"),

    # Portfolio
    path("test/portfolio", TestPortfolioView.as_view(), name="test_portfolio"),
    path("test/rebalance", TestRebalanceView.as_view(), name="test_rebalance"),
    path("test/risk", TestRiskView.as_view(), name="test_risk"),
]
