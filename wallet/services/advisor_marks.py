"""Advisor marks service for mapping recommendations into UI-friendly marks and thoughts."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time

from loguru import logger

from ..models import WalletAccount
from .advisor_recommendations import AdvisorRecommendationsService
from .financial_mcp import FinancialMcpError
from .llm_advice import LlmAdviceError


@dataclass(frozen=True)
class AdvisorMarksResult:
    marks: dict[str, str]
    thoughts: dict[str, str]


class AdvisorMarksService:
    """Maps advisor recommendation actions into UI-friendly marks and thoughts."""

    ACTION_TO_MARK: dict[str, str] = {
        "buy": "Buy",
        "buy_more": "Buy",
        "sell": "Sell",
        "hold": "Hold",
    }

    @classmethod
    def get_marks_and_thoughts(cls, account: WalletAccount) -> AdvisorMarksResult:
        started_at = time.perf_counter()
        logger.info("advisor_marks.get_marks_and_thoughts begin account_id={}", account.id)
        try:
            recommendations = asyncio.run(AdvisorRecommendationsService.get_portfolio_recommendations(account))
        except (FinancialMcpError, LlmAdviceError, ValueError, RuntimeError) as exc:
            logger.warning(
                "advisor_marks.get_marks_and_thoughts fallback account_id={} error_type={} error_repr={} total_ms={}",
                account.id,
                type(exc).__name__,
                repr(exc),
                round((time.perf_counter() - started_at) * 1000),
            )
            return AdvisorMarksResult(marks={}, thoughts={})
        result = cls._parse_recommendations(recommendations)
        logger.info(
            "advisor_marks.get_marks_and_thoughts success account_id={} marks={} thoughts={} total_ms={}",
            account.id,
            len(result.marks),
            len(result.thoughts),
            round((time.perf_counter() - started_at) * 1000),
        )
        return result

    @classmethod
    def _parse_recommendations(cls, recommendations: dict[str, object]) -> AdvisorMarksResult:
        marks: dict[str, str] = {}
        thoughts: dict[str, str] = {}

        actions = recommendations.get("actions")
        if isinstance(actions, list):
            cls._consume_actions(actions, marks, thoughts)

        return AdvisorMarksResult(marks=marks, thoughts=thoughts)

    @classmethod
    def _consume_actions(
        cls,
        actions: list[dict[str, object]],
        marks: dict[str, str],
        thoughts: dict[str, str],
    ) -> None:
        for action in actions:
            asset_id = str(action.get("asset_id", "")).strip()
            action_name = str(action.get("action", "")).strip()
            rationale = str(action.get("reason", "")).strip()
            if not asset_id:
                continue
            mark = cls.ACTION_TO_MARK.get(action_name, "Hold")
            marks[asset_id] = mark
            if rationale:
                thoughts[asset_id] = rationale
