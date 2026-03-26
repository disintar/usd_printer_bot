from __future__ import annotations

import json
import re
import time
from decimal import Decimal, InvalidOperation

from asgiref.sync import sync_to_async
from loguru import logger

from ..constants import TRADEABLE_ASSET_IDS
from ..models import AgentPreference, WalletAccount
from .advisor_preferences import AdvisorPreferencesService, AdvisorProfile
from .advisors import AdvisorsService
from .financial_mcp import FinancialMcpService, MarketSnapshot
from .llm_advice import LlmAdviceService
from .portfolio import PortfolioService, PortfolioSummary


class AdvisorRecommendationsService:
    """LLM-driven onboarding and portfolio recommendations using notebook tool schemas."""

    START_SNAPSHOT_LIMIT = 4
    PORTFOLIO_SNAPSHOT_LIMIT = 40

    SYSTEM_PROMPT = """
You are an investment decision engine for a retail portfolio app.

Rules:
- Use only the provided selected advisors, risk profile, portfolio state, balance, and market snapshots.
- Be concise and practical.
- Return results only through the forced tool.
- Keep reasons and summaries short.
- For portfolio recommendation requests, return exactly one action for every asset_id present in market_snapshots. Never omit an asset.
- For start requests, advisor_summaries must include exactly one item per selected advisor.
- Each advisor summary must be exactly 2 sentences and written in that advisor's persona/style voice.
- Sentence 1: character-style voice (wording should sound like that persona, not generic analyst prose).
- Sentence 2: concrete data-backed rationale citing market snapshots (upside/risk/diversification and risk profile).
- Avoid generic text like "balanced exposure" without concrete evidence.
""".strip()

    COMMON_PREFIX = (
        "Use the same output rules on every request. "
        "Interpret the payload as a portfolio decision task. Input JSON: "
    )

    START_TOOL_NAME = "emit_start_recommendations"
    START_TOOL_DESCRIPTION = "Return starting buy recommendations and advisor summaries."
    START_TOOL_SCHEMA: dict[str, object] = {
        "type": "object",
        "properties": {
            "buy_recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "asset_id": {"type": "string"},
                        "allocation_percent": {"type": "string"},
                        "verdict": {"type": "string", "enum": ["buy", "hold", "sell"]},
                        "reason": {"type": "string"},
                    },
                    "required": ["asset_id", "allocation_percent", "verdict", "reason"],
                    "additionalProperties": False,
                },
            },
            "advisor_summaries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "advisor_id": {"type": "string"},
                        "summary": {"type": "string"},
                    },
                    "required": ["advisor_id", "summary"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["buy_recommendations", "advisor_summaries"],
        "additionalProperties": False,
    }

    PORTFOLIO_TOOL_NAME = "emit_portfolio_actions"
    PORTFOLIO_TOOL_DESCRIPTION = (
        "Return exactly one action for every asset_id from market_snapshots."
    )
    PORTFOLIO_TOOL_SCHEMA: dict[str, object] = {
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "asset_id": {"type": "string"},
                        "action": {"type": "string", "enum": ["buy", "hold", "sell", "buy_more"]},
                        "reason": {"type": "string"},
                    },
                    "required": ["asset_id", "action", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["actions"],
        "additionalProperties": False,
    }

    ASSET_TOOL_NAME = "emit_asset_analysis"
    ASSET_TOOL_DESCRIPTION = "Return analysis for one asset."
    ASSET_TOOL_SCHEMA: dict[str, object] = {
        "type": "object",
        "properties": {
            "recommendation": {"type": "string", "enum": ["buy", "hold", "sell"]},
            "summary": {"type": "string"},
            "advisor_notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "advisor_id": {"type": "string"},
                        "thought": {"type": "string"},
                    },
                    "required": ["advisor_id", "thought"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["recommendation", "summary", "advisor_notes"],
        "additionalProperties": False,
    }

    @classmethod
    async def get_start_recommendations(
        cls,
        account: WalletAccount,
        deposit_amount: Decimal,
        risk_profile_override: str | None = None,
    ) -> dict[str, object]:
        started_at = time.perf_counter()
        profile = await AdvisorPreferencesService.get_profile(account)
        if isinstance(risk_profile_override, str) and risk_profile_override.strip():
            profile = AdvisorProfile(
                selected_advisors=list(profile.selected_advisors),
                advisor_weights=dict(profile.advisor_weights),
                risk_profile=risk_profile_override.strip().lower(),
                onboarding_completed=profile.onboarding_completed,
            )
        market_asset_ids = cls._start_market_asset_ids()
        logger.info(
            "advisor_start.begin account_id={} risk_profile={} advisors={} deposit_amount={} assets={}",
            account.id,
            profile.risk_profile,
            ",".join(profile.selected_advisors),
            deposit_amount.quantize(Decimal("0.01")),
            ",".join(market_asset_ids),
        )

        market_snapshots = await FinancialMcpService.list_market_snapshots(market_asset_ids)
        start_payload = cls._start_payload(profile, deposit_amount, market_snapshots)
        logger.info(
            "advisor_start.llm_request account_id={} payload={}",
            account.id,
            start_payload,
        )
        llm_output = await LlmAdviceService.complete_tool_input(
            system_prompt=cls.SYSTEM_PROMPT,
            user_prompt=cls._tool_user_prompt(
                start_payload
            ),
            tool_name=cls.START_TOOL_NAME,
            tool_description=cls.START_TOOL_DESCRIPTION,
            input_schema=cls.START_TOOL_SCHEMA,
        )
        logger.info(
            "advisor_start.llm_response account_id={} payload={}",
            account.id,
            llm_output,
        )
        result = cls._parse_start_response(llm_output, profile)
        await cls._store_start_recommendations(account, deposit_amount, result)
        logger.info(
            "advisor_start.success account_id={} buy_recommendations={} advisor_summaries={} total_ms={}",
            account.id,
            len(result["buy_recommendations"]),
            len(result["advisor_summaries"]),
            cls._elapsed_ms(started_at),
        )
        return result

    @classmethod
    async def get_saved_start_recommendations(cls, account: WalletAccount) -> dict[str, object] | None:
        preference, _ = await AgentPreference.objects.aget_or_create(
            account=account,
            defaults={
                "selected_agents": AgentPreference.default_selected_advisors(),
                "allocation": AgentPreference.default_advisor_weights(),
                "selected_advisors": AgentPreference.default_selected_advisors(),
                "advisor_weights": AgentPreference.default_advisor_weights(),
                "risk_profile": AgentPreference.default_risk_profile(),
            },
        )
        stored = preference.initial_portfolio
        if not isinstance(stored, dict) or not stored:
            return None

        raw_recommendations = stored.get("buy_recommendations")
        raw_summaries = stored.get("advisor_summaries")
        if not isinstance(raw_recommendations, list) or not isinstance(raw_summaries, list):
            return None
        return {
            "buy_recommendations": [cls._parse_start_recommendation(item) for item in raw_recommendations],
            "advisor_summaries": [
                {
                    "advisor_id": str(item.get("advisor_id", "")).strip(),
                    "summary": str(item.get("summary", "")).strip(),
                }
                for item in raw_summaries
                if isinstance(item, dict)
                and str(item.get("advisor_id", "")).strip()
                and str(item.get("summary", "")).strip()
            ],
        }

    @classmethod
    async def get_portfolio_recommendations(cls, account: WalletAccount) -> dict[str, object]:
        started_at = time.perf_counter()
        profile = await AdvisorPreferencesService.get_profile(account)
        portfolio = await sync_to_async(PortfolioService.get_portfolio, thread_sensitive=True)(account)
        market_asset_ids = cls._portfolio_market_asset_ids(portfolio)
        logger.info(
            "advisor_portfolio.begin account_id={} risk_profile={} advisors={} cash_balance={} assets={}",
            account.id,
            profile.risk_profile,
            ",".join(profile.selected_advisors),
            account.cash_balance.quantize(Decimal("0.01")),
            ",".join(market_asset_ids),
        )

        market_snapshots = await FinancialMcpService.list_market_snapshots(market_asset_ids)
        portfolio_payload = cls._portfolio_payload(profile, portfolio, market_snapshots, account.cash_balance)
        logger.info(
            "advisor_portfolio.llm_request account_id={} payload={}",
            account.id,
            portfolio_payload,
        )
        llm_output = await LlmAdviceService.complete_tool_input(
            system_prompt=cls.SYSTEM_PROMPT,
            user_prompt=cls._tool_user_prompt(
                portfolio_payload
            ),
            tool_name=cls.PORTFOLIO_TOOL_NAME,
            tool_description=cls.PORTFOLIO_TOOL_DESCRIPTION,
            input_schema=cls.PORTFOLIO_TOOL_SCHEMA,
        )
        logger.info(
            "advisor_portfolio.llm_response account_id={} payload={}",
            account.id,
            llm_output,
        )
        result = cls._parse_portfolio_response(llm_output)
        result["actions"] = cls._ensure_portfolio_action_coverage(
            result["actions"],
            market_asset_ids,
        )
        logger.info(
            "advisor_portfolio.success account_id={} actions={} total_ms={}",
            account.id,
            len(result["actions"]),
            cls._elapsed_ms(started_at),
        )
        return result

    @classmethod
    async def get_asset_analysis(cls, account: WalletAccount, asset_id: str) -> dict[str, object]:
        started_at = time.perf_counter()
        logger.info(
            "advisor_asset_analysis.begin account_id={} asset_id={}",
            account.id,
            asset_id,
        )
        profile = await AdvisorPreferencesService.get_profile(account)
        logger.debug(
            "advisor_asset_analysis.profile account_id={} asset_id={} risk_profile={} advisors={}",
            account.id,
            asset_id,
            profile.risk_profile,
            ",".join(profile.selected_advisors),
        )
        market_snapshot = (await FinancialMcpService.list_market_snapshots([asset_id]))[0]
        logger.debug(
            "advisor_asset_analysis.market account_id={} asset_id={} symbol={} price={} target_consensus={} upside_percent={}",
            account.id,
            asset_id,
            market_snapshot.symbol,
            market_snapshot.price,
            market_snapshot.target_consensus,
            market_snapshot.upside_percent.quantize(Decimal("0.01")),
        )
        asset_prompt = cls._asset_user_prompt(profile, market_snapshot)
        logger.debug(
            "advisor_asset_analysis.llm_request account_id={} asset_id={} prompt_chars={}",
            account.id,
            asset_id,
            len(asset_prompt),
        )
        llm_output = await LlmAdviceService.complete_tool_input(
            system_prompt=cls._asset_system_prompt(),
            user_prompt=asset_prompt,
            tool_name=cls.ASSET_TOOL_NAME,
            tool_description=cls.ASSET_TOOL_DESCRIPTION,
            input_schema=cls.ASSET_TOOL_SCHEMA,
        )
        logger.debug(
            "advisor_asset_analysis.llm_response account_id={} asset_id={} keys={}",
            account.id,
            asset_id,
            ",".join(sorted(llm_output.keys())),
        )
        result = cls._parse_asset_analysis(asset_id, profile, llm_output)
        logger.info(
            "advisor_asset_analysis.success account_id={} asset_id={} recommendation={} notes={} total_ms={}",
            account.id,
            asset_id,
            result.get("recommendation"),
            len(result.get("advisor_notes", [])),
            cls._elapsed_ms(started_at),
        )
        return result

    @classmethod
    def _start_market_asset_ids(cls) -> list[str]:
        return list(TRADEABLE_ASSET_IDS[: cls.START_SNAPSHOT_LIMIT])

    @classmethod
    def _portfolio_market_asset_ids(cls, portfolio: PortfolioSummary) -> list[str]:
        del portfolio
        return list(TRADEABLE_ASSET_IDS[: cls.PORTFOLIO_SNAPSHOT_LIMIT])

    @classmethod
    def _start_payload(
        cls,
        profile: AdvisorProfile,
        deposit_amount: Decimal,
        market_snapshots: list[MarketSnapshot],
    ) -> dict[str, object]:
        normalized_amount = str(deposit_amount.quantize(Decimal("0.01")))
        return {
            "request_type": "start",
            "selected_advisors": cls._selected_advisors_payload(profile),
            "risk_profile": profile.risk_profile,
            "cash_balance_usdt": normalized_amount,
            "portfolio": {
                "total_balance_usdt": normalized_amount,
                "pnl_percent": "0.00",
                "pnl_absolute": "0.00",
                "assets": [],
            },
            "market_snapshots": [cls._snapshot_payload(item) for item in market_snapshots],
        }

    @classmethod
    def _portfolio_payload(
        cls,
        profile: AdvisorProfile,
        portfolio: PortfolioSummary,
        market_snapshots: list[MarketSnapshot],
        cash_balance: Decimal,
    ) -> dict[str, object]:
        return {
            "request_type": "recommendations",
            "selected_advisors": cls._selected_advisors_payload(profile),
            "risk_profile": profile.risk_profile,
            "cash_balance_usdt": str(cash_balance.quantize(Decimal("0.01"))),
            "portfolio": {
                "total_balance_usdt": str(portfolio.total_balance_usdt),
                "pnl_percent": str(portfolio.pnl_percent),
                "pnl_absolute": str(portfolio.pnl_absolute),
                "assets": [
                    {
                        "asset_id": asset.asset_id,
                        "quantity": str(asset.quantity),
                        "value_usdt": str(asset.value_usdt),
                        "allocation_percent": str(asset.allocation_percent),
                    }
                    for asset in portfolio.assets
                    if asset.asset_id in TRADEABLE_ASSET_IDS
                ],
            },
            "market_snapshots": [cls._snapshot_payload(item) for item in market_snapshots],
        }

    @classmethod
    def _tool_user_prompt(cls, payload: dict[str, object]) -> str:
        return cls.COMMON_PREFIX + json.dumps(payload, ensure_ascii=True)

    @classmethod
    def _selected_advisors_payload(cls, profile: AdvisorProfile) -> list[dict[str, object]]:
        advisors_by_id = {advisor.advisor_id: advisor for advisor in AdvisorsService.list_advisors()}
        return [
            {
                "id": advisor.advisor_id,
                "name": advisor.name,
                "category": advisor.category,
                "role": advisor.role,
                "style": advisor.style,
                "tags": advisor.tags,
                "primary_tag": advisor.primary_tag,
            }
            for advisor_id in profile.selected_advisors
            if (advisor := advisors_by_id.get(advisor_id)) is not None
        ]

    @staticmethod
    def _snapshot_payload(snapshot: MarketSnapshot) -> dict[str, object]:
        return {
            "asset_id": snapshot.asset_id,
            "price": str(snapshot.price),
            "upside_percent": str(snapshot.upside_percent.quantize(Decimal("0.01"))),
        }

    @classmethod
    def _parse_start_response(
        cls,
        payload: dict[str, object],
        profile: AdvisorProfile,
    ) -> dict[str, object]:
        raw_recommendations = payload.get("buy_recommendations")
        if not isinstance(raw_recommendations, list) or not raw_recommendations:
            raise ValueError("LLM start response is missing buy_recommendations")
        recommendations = [
            cls._parse_start_recommendation(item)
            for item in raw_recommendations
        ]
        total = sum(Decimal(item["allocation_percent"]) for item in recommendations)
        if total != Decimal("100.00"):
            raise ValueError("LLM start allocations must sum to 100.00")

        raw_summaries = payload.get("advisor_summaries")
        if not isinstance(raw_summaries, list) or not raw_summaries:
            raise ValueError("LLM start response is missing advisor_summaries")

        selected_advisors_payload = cls._selected_advisors_payload(profile)
        advisors_by_id = {
            str(item.get("id")): item for item in selected_advisors_payload if str(item.get("id", "")).strip()
        }
        allowed_advisors = {advisor["id"] for advisor in selected_advisors_payload}
        allowed_name_map = {
            str(advisor["name"]).strip().lower(): str(advisor["id"])
            for advisor in selected_advisors_payload
            if str(advisor.get("name", "")).strip() and str(advisor.get("id", "")).strip()
        }
        advisor_summaries: list[dict[str, str]] = []
        seen_advisors: set[str] = set()
        for item in raw_summaries:
            if not isinstance(item, dict):
                raise ValueError("LLM advisor summary item must be an object")
            raw_advisor_id = str(item.get("advisor_id", "")).strip()
            advisor_id = raw_advisor_id
            if advisor_id not in allowed_advisors:
                advisor_id = allowed_name_map.get(raw_advisor_id.lower(), "")
            summary = str(item.get("summary", "")).strip()
            if advisor_id not in allowed_advisors or not summary:
                raise ValueError("LLM advisor summary is invalid")
            summary = cls._ensure_two_sentence_summary(
                summary=summary,
                advisor=advisors_by_id.get(advisor_id, {}),
                recommendations=recommendations,
                risk_profile=profile.risk_profile,
            )
            if advisor_id in seen_advisors:
                continue
            seen_advisors.add(advisor_id)
            advisor_summaries.append({"advisor_id": advisor_id, "summary": summary})

        missing_advisor_ids = [advisor_id for advisor_id in allowed_advisors if advisor_id not in seen_advisors]
        if missing_advisor_ids:
            raise ValueError(
                f"LLM advisor summaries are incomplete; missing: {', '.join(sorted(missing_advisor_ids))}"
            )

        return {
            "buy_recommendations": recommendations,
            "advisor_summaries": advisor_summaries,
        }

    @classmethod
    async def _store_start_recommendations(
        cls,
        account: WalletAccount,
        deposit_amount: Decimal,
        result: dict[str, object],
    ) -> None:
        preference, _ = await AgentPreference.objects.aget_or_create(
            account=account,
            defaults={
                "selected_agents": AgentPreference.default_selected_advisors(),
                "allocation": AgentPreference.default_advisor_weights(),
                "selected_advisors": AgentPreference.default_selected_advisors(),
                "advisor_weights": AgentPreference.default_advisor_weights(),
                "risk_profile": AgentPreference.default_risk_profile(),
            },
        )
        preference.initial_portfolio = {
            "deposit_amount": str(deposit_amount.quantize(Decimal("0.01"))),
            "buy_recommendations": result["buy_recommendations"],
            "advisor_summaries": result["advisor_summaries"],
        }
        await preference.asave(update_fields=["initial_portfolio", "updated_at"])

    @classmethod
    def _parse_start_recommendation(cls, item: object) -> dict[str, str]:
        if not isinstance(item, dict):
            raise ValueError("LLM buy recommendation item must be an object")
        asset_id = cls._normalize_asset_id(item.get("asset_id"))
        verdict = str(item.get("verdict", "")).strip().lower()
        reason = str(item.get("reason", "")).strip()
        allocation_percent = cls._parse_allocation_percent(item.get("allocation_percent", "0"))

        # Normalize common variations
        if verdict in {"bullish", "long", "buy_more", "strong_buy", "outperform", "accumulate"}:
            verdict = "buy"
        elif verdict in {"bearish", "short", "sell_more", "underperform", "reduce"}:
            verdict = "sell"
        elif verdict not in {"buy", "hold", "sell"}:
            logger.warning("start_recommendation.invalid_verdict verdict='{}' item={}", verdict, item)
            verdict = "hold"  # Default to hold for unknown verdicts
        if not reason:
            raise ValueError("LLM returned empty reason")
        if allocation_percent < Decimal("0"):
            raise ValueError("LLM returned negative allocation_percent")

        return {
            "asset_id": asset_id,
            "allocation_percent": str(allocation_percent),
            "verdict": verdict,
            "reason": reason,
        }

    @staticmethod
    def _parse_allocation_percent(raw_value: object) -> Decimal:
        raw_text = str(raw_value).strip()
        if raw_text == "":
            raise ValueError("LLM returned invalid allocation_percent")
        normalized = raw_text.replace("%", "").replace(",", ".").strip()
        try:
            return Decimal(normalized).quantize(Decimal("0.01"))
        except InvalidOperation as exc:
            raise ValueError("LLM returned invalid allocation_percent") from exc

    @staticmethod
    def _sentence_count(text: str) -> int:
        chunks = [chunk.strip() for chunk in re.split(r"[.!?]+(?:\s+|$)", text.strip()) if chunk.strip()]
        return len(chunks)

    @classmethod
    def _ensure_two_sentence_summary(
        cls,
        *,
        summary: str,
        advisor: dict[str, object],
        recommendations: list[dict[str, str]],
        risk_profile: str,
    ) -> str:
        if cls._sentence_count(summary) >= 2:
            return summary
        advisor_name = str(advisor.get("name", "This advisor")).strip() or "This advisor"
        style_items = advisor.get("style")
        style_hint = ""
        if isinstance(style_items, list) and style_items:
            style_hint = str(style_items[0]).strip().rstrip(".")
        top_assets = [item.get("asset_id", "") for item in recommendations[:3] if item.get("asset_id", "")]
        top_assets_text = ", ".join(top_assets) if top_assets else "the top-conviction assets"
        second_sentence = (
            f"Using live market snapshots, upside estimates, and {risk_profile} risk constraints, "
            f"{advisor_name} favors {top_assets_text} with disciplined diversification."
        )
        if style_hint:
            second_sentence = (
                f"Using live market snapshots, upside estimates, and {risk_profile} risk constraints, "
                f"{advisor_name} favors {top_assets_text} with disciplined diversification in a style that is {style_hint}."
            )
        return f"{summary.rstrip('. ')}. {second_sentence}"

    @classmethod
    def _parse_portfolio_response(cls, payload: dict[str, object]) -> dict[str, object]:
        raw_actions = payload.get("actions")
        if not isinstance(raw_actions, list):
            raise ValueError("LLM portfolio response is missing actions")
        return {
            "actions": [cls._parse_portfolio_action(item) for item in raw_actions],
        }

    @classmethod
    def _parse_portfolio_action(cls, item: object) -> dict[str, str]:
        if not isinstance(item, dict):
            raise ValueError("LLM portfolio action item must be an object")
        asset_id = cls._normalize_asset_id(item.get("asset_id"))
        action = str(item.get("action", "")).strip().lower()
        reason = str(item.get("reason", "")).strip()
        if action not in {"buy", "hold", "sell", "buy_more"}:
            raise ValueError(f"LLM returned unsupported action '{action}'")
        if not reason:
            raise ValueError("LLM returned empty reason")
        return {
            "asset_id": asset_id,
            "action": action,
            "reason": reason,
        }

    @classmethod
    def _ensure_portfolio_action_coverage(
        cls,
        actions: list[dict[str, str]],
        expected_asset_ids: list[str],
    ) -> list[dict[str, str]]:
        actions_by_asset_id = {
            item["asset_id"]: item
            for item in actions
            if item.get("asset_id") in expected_asset_ids
        }
        covered_actions: list[dict[str, str]] = []
        for asset_id in expected_asset_ids:
            existing = actions_by_asset_id.get(asset_id)
            if existing is not None:
                covered_actions.append(existing)
                continue
            covered_actions.append(
                {
                    "asset_id": asset_id,
                    "action": "hold",
                    "reason": "No strong change signal right now.",
                }
            )
        return covered_actions

    @staticmethod
    def _normalize_asset_id(raw_asset_id: object) -> str:
        normalized = str(raw_asset_id).strip()
        asset_id = next(
            (valid for valid in TRADEABLE_ASSET_IDS if valid.lower() == normalized.lower()),
            "",
        )
        if asset_id not in TRADEABLE_ASSET_IDS:
            raise ValueError(f"LLM returned unsupported asset_id '{normalized}'")
        return asset_id

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)

    @classmethod
    def _asset_system_prompt(cls) -> str:
        return (
            "You are an asset analysis engine. "
            "Return output through the forced tool only. "
            "recommendation must be buy, hold, or sell. "
            "advisor_notes must include one item per selected adviser. Keep text short."
        )

    @classmethod
    def _asset_user_prompt(
        cls,
        profile: AdvisorProfile,
        market_snapshot: MarketSnapshot,
    ) -> str:
        payload = {
            "advisors": cls._selected_advisors_payload(profile),
            "risk": profile.risk_profile,
            "asset": {
                "id": market_snapshot.asset_id,
                "price": str(market_snapshot.price),
                "upside_pct": str(market_snapshot.upside_percent.quantize(Decimal("0.01"))),
            },
        }
        return json.dumps(payload, ensure_ascii=True)

    @classmethod
    def _parse_asset_analysis(
        cls,
        asset_id: str,
        profile: AdvisorProfile,
        payload: dict[str, object],
    ) -> dict[str, object]:
        recommendation = str(payload.get("recommendation", "")).strip().lower()
        # Normalize common variations
        if recommendation in {"bullish", "long", "buy_more", "strong_buy", "outperform"}:
            recommendation = "buy"
        elif recommendation in {"bearish", "short", "sell_more", "underperform"}:
            recommendation = "sell"
        elif recommendation not in {"buy", "hold", "sell"}:
            logger.warning(
                "asset_analysis.invalid_recommendation asset_id={} recommendation='{}' payload={}",
                asset_id,
                recommendation,
                payload,
            )
            raise ValueError(f"LLM asset analysis recommendation is invalid: {recommendation}")

        summary = str(payload.get("summary", payload.get("analysis", ""))).strip()
        if not summary:
            logger.warning("asset_analysis.empty_summary asset_id={} payload={}", asset_id, payload)
            summary = f"Analysis for {asset_id} based on selected advisors."

        raw_notes = payload.get("advisor_notes", payload.get("notes", []))
        if not isinstance(raw_notes, list) or not raw_notes:
            logger.warning("asset_analysis.missing_notes asset_id={} payload={}", asset_id, payload)
            raw_notes = []

        selected_ids = set(profile.selected_advisors)
        advisors_by_id = {advisor.advisor_id: advisor for advisor in AdvisorsService.list_advisors()}
        advisor_notes: list[dict[str, str]] = []
        for note in raw_notes:
            if not isinstance(note, dict):
                continue
            note_advisor_id = str(note.get("advisor_id", "")).strip()
            note_thought = str(note.get("thought", "")).strip()
            if note_advisor_id not in selected_ids or not note_thought:
                continue
            advisor = advisors_by_id.get(note_advisor_id)
            if advisor is None:
                continue
            advisor_notes.append(
                {
                    "advisor_id": note_advisor_id,
                    "name": advisor.name,
                    "thought": note_thought,
                }
            )

        if not advisor_notes:
            logger.warning("asset_analysis.no_valid_notes asset_id={} selected_ids={}", asset_id, selected_ids)
            # Create a default note if none provided
            advisor_notes = [{
                "advisor_id": list(selected_ids)[0] if selected_ids else "default",
                "name": "Advisor",
                "thought": summary[:200] if summary else f"Analysis of {asset_id}",
            }]

        return {
            "asset_id": asset_id,
            "recommendation": recommendation,
            "summary": summary,
            "advisor_notes": advisor_notes,
        }
