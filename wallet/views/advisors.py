"""Advisor views: registry, preferences, and recommendations."""
from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from loguru import logger

from ..constants import RISK_PROFILE_IDS, TRADEABLE_ASSET_IDS
from ..models import TelegramIdentity
from ..services.advisor_preferences import AdvisorPreferencesService
from ..services.advisor_recommendations import AdvisorRecommendationsService
from ..services.advisors import AdvisorsService
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
class AdvisorsListView(View):
    """GET /advisors/list - List configured advisor personas."""

    async def get(self, request: HttpRequest) -> JsonResponse:
        primary_tag = request.GET.get("primary_tag")
        try:
            advisors = await run_sync(
                lambda: AdvisorsService.list_advisors_by_primary_tag(primary_tag)
            )
        except ValueError as exc:
            return error_response(str(exc), 400)
        return json_response(
            {
                "advisors": [
                    {
                        "id": advisor.advisor_id,
                        "name": advisor.name,
                        "category": advisor.category,
                        "role": advisor.role,
                        "style": advisor.style,
                        "tags": advisor.tags,
                        "primary_tag": advisor.primary_tag,
                        "tabler_icon": advisor.tabler_icon,
                    }
                    for advisor in advisors
                ]
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class AdvisorPreferencesView(View):
    """GET/POST /advisors/preferences - View and update advisor preferences."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        profile = await AdvisorPreferencesService.get_profile(account)
        return json_response(
            {
                "selected_advisors": profile.selected_advisors,
                "advisor_weights": profile.advisor_weights,
                "risk_profile": profile.risk_profile,
                "onboarding_completed": profile.onboarding_completed,
            }
        )

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
        except ValueError:
            return error_response("Invalid JSON", 400)

        selected_advisors = data.get("selected_advisors")
        advisor_weights = data.get("advisor_weights")
        risk_profile = data.get("risk_profile")

        if not isinstance(selected_advisors, list):
            return error_response("selected_advisors must be a list", 400)
        if advisor_weights is not None and not isinstance(advisor_weights, dict):
            return error_response("advisor_weights must be an object", 400)
        if not isinstance(risk_profile, str):
            return error_response("risk_profile must be a string", 400)

        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        try:
            profile = await AdvisorPreferencesService.update_profile(
                account,
                selected_advisors=selected_advisors,
                advisor_weights=advisor_weights,
                risk_profile=risk_profile,
            )
        except ValueError as exc:
            return error_response(str(exc), 400)

        return json_response(
            {
                "selected_advisors": profile.selected_advisors,
                "advisor_weights": profile.advisor_weights,
                "risk_profile": profile.risk_profile,
                "onboarding_completed": profile.onboarding_completed,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class AdvisorStartView(View):
    """POST /advisors/start - Get initial buy recommendations for a deposit size."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        result = await AdvisorRecommendationsService.get_saved_start_recommendations(account)
        if result is None:
            return error_response("Initial portfolio not found", 404)
        return json_response(result)

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        try:
            data = parse_json(request)
        except ValueError:
            return error_response("Invalid JSON", 400)

        logger.info(
            "AdvisorStartView.post request user_id={} payload={}",
            identity.telegram_user_id,
            data,
        )
        deposit_amount = data.get("deposit_amount")
        risk_profile = data.get("risk_profile")
        try:
            deposit_decimal = Decimal(str(deposit_amount))
        except (InvalidOperation, TypeError):
            return error_response("deposit_amount must be numeric", 400)

        if deposit_decimal <= 0:
            return error_response("deposit_amount must be positive", 400)
        if risk_profile is not None:
            if not isinstance(risk_profile, str):
                return error_response("risk_profile must be a string", 400)
            normalized_risk_profile = risk_profile.strip().lower()
            if normalized_risk_profile not in RISK_PROFILE_IDS:
                return error_response(
                    f"Invalid risk_profile. Must be one of: {', '.join(RISK_PROFILE_IDS)}",
                    400,
                )
        else:
            normalized_risk_profile = None

        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        try:
            result = await AdvisorRecommendationsService.get_start_recommendations(
                account,
                deposit_decimal,
                risk_profile_override=normalized_risk_profile,
            )
            await AdvisorPreferencesService.mark_onboarding_completed(account)
        except (FinancialMcpError, LlmAdviceError, ValueError) as exc:
            return error_response(str(exc), 503)

        logger.info(
            "AdvisorStartView.post response user_id={} buy_recommendations={} advisor_summaries={} payload={}",
            identity.telegram_user_id,
            len(result.get("buy_recommendations", [])),
            len(result.get("advisor_summaries", [])),
            result,
        )
        return json_response(result)


@method_decorator(csrf_exempt, name="dispatch")
class AdvisorOnboardingResetView(View):
    """POST /advisors/onboarding/reset - Reset advisor onboarding choices only."""

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        profile = await AdvisorPreferencesService.reset_onboarding(account)
        return json_response(
            {
                "selected_advisors": profile.selected_advisors,
                "advisor_weights": profile.advisor_weights,
                "risk_profile": profile.risk_profile,
                "onboarding_completed": profile.onboarding_completed,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class AdvisorPortfolioRecommendationsView(View):
    """POST /advisors/recommendations - Get current portfolio recommendations."""

    @require_auth
    async def post(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        account = await get_account_for_identity(identity)
        if account is None:
            return error_response("Account not found", 404)

        logger.info(
            "AdvisorPortfolioRecommendationsView.post request user_id={} path={}",
            identity.telegram_user_id,
            request.path,
        )
        try:
            result = await AdvisorRecommendationsService.get_portfolio_recommendations(account)
        except (FinancialMcpError, LlmAdviceError, ValueError) as exc:
            return error_response(str(exc), 503)

        logger.info(
            "AdvisorPortfolioRecommendationsView.post response user_id={} actions={} payload={}",
            identity.telegram_user_id,
            len(result.get("actions", [])),
            result,
        )
        return json_response(result)


@method_decorator(csrf_exempt, name="dispatch")
class AdvisorAssetAnalysisView(View):
    """GET /advisors/analysis?asset_id=X - Adviser analysis for a specific asset."""

    @require_auth
    async def get(self, request: HttpRequest, identity: TelegramIdentity) -> JsonResponse:
        started_at = time.perf_counter()
        asset_id = str(request.GET.get("asset_id", "")).strip()
        query_string = request.META.get("QUERY_STRING", "")
        request_id = str(request.META.get("HTTP_X_REQUEST_ID", "")).strip() or "-"
        logger.info(
            "AdvisorAssetAnalysisView.get: user_id={} path={} query={} request_id={} asset_id={}",
            identity.telegram_user_id,
            request.path,
            query_string,
            request_id,
            asset_id,
        )
        logger.debug(
            "AdvisorAssetAnalysisView.get request_debug user_id={} asset_id={} headers={{user_agent={}, accept={}, content_type={}}}",
            identity.telegram_user_id,
            asset_id,
            request.META.get("HTTP_USER_AGENT", ""),
            request.META.get("HTTP_ACCEPT", ""),
            request.META.get("CONTENT_TYPE", ""),
        )
        if asset_id not in TRADEABLE_ASSET_IDS:
            logger.warning(
                "AdvisorAssetAnalysisView.get: invalid asset_id={} user_id={} request_id={} allowed={}",
                asset_id,
                identity.telegram_user_id,
                request_id,
                ",".join(TRADEABLE_ASSET_IDS),
            )
            return error_response(
                f"Invalid asset_id. Must be one of: {', '.join(TRADEABLE_ASSET_IDS)}",
                400,
            )

        account = await get_account_for_identity(identity)
        if account is None:
            logger.warning(
                "AdvisorAssetAnalysisView.get: account not found user_id={} request_id={} asset_id={}",
                identity.telegram_user_id,
                request_id,
                asset_id,
            )
            return error_response("Account not found", 404)

        logger.debug(
            "AdvisorAssetAnalysisView.get: context user_id={} request_id={} account_id={} asset_id={}",
            identity.telegram_user_id,
            request_id,
            account.id,
            asset_id,
        )
        try:
            result = await AdvisorRecommendationsService.get_asset_analysis(account, asset_id)
        except (FinancialMcpError, LlmAdviceError, ValueError) as exc:
            logger.exception(
                "AdvisorAssetAnalysisView.get: analysis failed user_id={} request_id={} account_id={} asset_id={} error_type={} error_repr={} total_ms={}",
                identity.telegram_user_id,
                request_id,
                account.id,
                asset_id,
                type(exc).__name__,
                repr(exc),
                round((time.perf_counter() - started_at) * 1000),
            )
            return error_response(str(exc), 503)

        notes = result.get("advisor_notes")
        notes_count = len(notes) if isinstance(notes, list) else 0
        logger.info(
            "AdvisorAssetAnalysisView.get: success user_id={} request_id={} account_id={} asset_id={} recommendation={} notes={} total_ms={}",
            identity.telegram_user_id,
            request_id,
            account.id,
            asset_id,
            result.get("recommendation"),
            notes_count,
            round((time.perf_counter() - started_at) * 1000),
        )
        logger.debug(
            "AdvisorAssetAnalysisView.get response_debug user_id={} request_id={} asset_id={} response_keys={}",
            identity.telegram_user_id,
            request_id,
            asset_id,
            ",".join(sorted(result.keys())),
        )
        return json_response(result)
