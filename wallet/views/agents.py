"""AI Agents views: agents, select, allocation, reasoning."""
from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from ..constants import SUPPORTED_ASSET_IDS
from ..models import TelegramIdentity, WalletAccount
from ..services.ai_agents import AIAgentsService
from ..services.financial_mcp import FinancialMcpError
from ..services.llm_advice import LlmAdviceError
from .base import (
    error_response,
    get_account_for_identity,
    json_response,
    parse_json,
    require_auth,
    run_sync,
)


@method_decorator(csrf_exempt, name="dispatch")
class TestAgentsView(View):
    """GET /test/agents - Get AI agents information."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        result = await AIAgentsService.get_active_agents_result(account)
        return json_response(
            {
                "active_agents": result.active_agents,
                "selected_agents": result.selected_agents,
                "allocation": result.allocation,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class AgentsActiveView(View):
    """GET /agents/active - Get number of active agents across all users."""

    async def get(self, request: HttpRequest) -> JsonResponse:
        users_count = await run_sync(WalletAccount.objects.count)
        agents_active = users_count * 3
        return json_response({"agents_active": agents_active})


@method_decorator(csrf_exempt, name="dispatch")
class TestAgentsSelectView(View):
    """POST /test/agents/select - Select which AI agents to use."""

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
        except ValueError:
            return error_response("Invalid JSON", 400)

        selected_agents = data.get("selected_agents")
        if not isinstance(selected_agents, list) or not selected_agents:
            return error_response("selected_agents must be a non-empty list", 400)

        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        try:
            await AIAgentsService.select_agents(account, selected_agents)
        except ValueError as exc:
            return error_response(str(exc), 400)

        return json_response({"selected_agents": selected_agents})


@method_decorator(csrf_exempt, name="dispatch")
class TestAgentsAllocationView(View):
    """GET/POST /test/agents/allocation - Get or update agent allocation."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        allocation = await AIAgentsService.get_allocation(account)
        return json_response({"allocation": allocation})

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
        except ValueError:
            return error_response("Invalid JSON", 400)

        allocation = data.get("allocation")
        if not isinstance(allocation, dict):
            return error_response("allocation must be an object", 400)

        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        try:
            updated = await AIAgentsService.update_allocation(account, allocation)
        except ValueError as exc:
            return error_response(str(exc), 400)

        return json_response({"allocation": updated})


@method_decorator(csrf_exempt, name="dispatch")
class TestAgentsReasoningView(View):
    """GET /test/agents/reasoning - Get AI agent reasoning for an asset."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        asset_id = request.GET.get("asset_id")
        if not asset_id:
            return error_response("asset_id query parameter is required", 400)

        if asset_id not in SUPPORTED_ASSET_IDS:
            return error_response(
                f"Invalid asset_id. Must be one of: {', '.join(SUPPORTED_ASSET_IDS)}",
                400,
            )

        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        try:
            reasoning = await AIAgentsService.get_reasoning(account, asset_id)
        except (FinancialMcpError, LlmAdviceError, ValueError) as exc:
            return error_response(str(exc), 503)
        return json_response(
            {
                "asset_id": reasoning.asset_id,
                "reasoning": reasoning.reasoning,
                "recommendation": reasoning.recommendation,
            }
        )
