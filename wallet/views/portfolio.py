"""Portfolio views: portfolio, rebalance, risk."""
from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from ..models import TelegramIdentity
from ..services.portfolio import PortfolioService
from ..services.risk import RiskService
from .base import error_response, get_account_for_identity, json_response, require_auth, run_sync


@method_decorator(csrf_exempt, name="dispatch")
class TestPortfolioView(View):
    """GET /test/portfolio - Get portfolio summary."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        portfolio = await run_sync(lambda: PortfolioService.get_portfolio(account))
        return json_response(
            {
                "total_balance_usdt": str(portfolio.total_balance_usdt),
                "pnl_percent": str(portfolio.pnl_percent),
                "pnl_absolute": str(portfolio.pnl_absolute),
                "allocation": portfolio.allocation,
                "assets": [
                    {
                        "asset_id": asset.asset_id,
                        "quantity": str(asset.quantity),
                        "value_usdt": str(asset.value_usdt),
                        "allocation_percent": str(asset.allocation_percent),
                    }
                    for asset in portfolio.assets
                ],
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class TestRebalanceView(View):
    """POST /test/rebalance - Get rebalancing actions."""

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        result = await run_sync(lambda: PortfolioService.rebalance(account))
        return json_response(result)


@method_decorator(csrf_exempt, name="dispatch")
class TestRiskView(View):
    """GET /test/risk - Get risk assessment."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        risk = await run_sync(lambda: RiskService.get_risk_assessment(account))
        return json_response(
            {
                "risk_score": str(risk.risk_score),
                "risk_level": risk.risk_level,
                "max_position_percent": str(risk.max_position_percent),
                "cash_percent": str(risk.cash_percent),
                "equity_usdt": str(risk.equity_usdt),
            }
        )
