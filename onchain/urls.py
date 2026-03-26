from django.urls import path

from .views import (
    OnchainAddressView,
    OnchainBalanceView,
    OnchainBuyView,
    OnchainDeployView,
    OnchainOrderView,
    OnchainOrdersView,
    OnchainSellView,
    OnchainWalletCreateView,
    OnchainWithdrawView,
)

app_name = "onchain"

urlpatterns = [
    path("onchain/wallet/create", OnchainWalletCreateView.as_view(), name="wallet_create"),
    path("onchain/deploy", OnchainDeployView.as_view(), name="deploy"),
    path("onchain/address", OnchainAddressView.as_view(), name="address"),
    path("onchain/balance", OnchainBalanceView.as_view(), name="balance"),
    path("onchain/withdraw", OnchainWithdrawView.as_view(), name="withdraw"),
    path("onchain/buy", OnchainBuyView.as_view(), name="buy"),
    path("onchain/sell", OnchainSellView.as_view(), name="sell"),
    path("onchain/orders", OnchainOrdersView.as_view(), name="orders"),
    path("onchain/order/<int:order_id>", OnchainOrderView.as_view(), name="order"),
]
