"""Async AI agents service for managing AI agents, their selections, and allocations."""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..models import AgentPreference, WalletAccount
from .advisors import AdvisorsService
from .financial_mcp import FinancialMcpService
from .llm_advice import LlmAdviceService
from .prices import PricesService


@dataclass(frozen=True)
class AgentInfo:
    """Information about an AI agent."""

    agent_id: str
    name: str
    description: str


@dataclass(frozen=True)
class ActiveAgentsResult:
    """Result containing active agents information."""

    active_agents: list[str]
    selected_agents: list[str]
    allocation: dict[str, float]


@dataclass(frozen=True)
class AgentReasoning:
    """AI agent reasoning for an asset."""

    asset_id: str
    reasoning: list[str]
    recommendation: str


class AIAgentsService:
    """Async service for managing AI agents, their selections, and allocations."""

    @classmethod
    def get_active_agents(cls) -> list[AgentInfo]:
        """Get advisors from Configure Your Team as active agents."""
        return [
            AgentInfo(agent_id=advisor.advisor_id, name=advisor.name, description=advisor.role)
            for advisor in AdvisorsService.list_advisors()
        ]

    @classmethod
    async def get_active_agents_result(cls, account: WalletAccount) -> ActiveAgentsResult:
        """Get active agents based only on Configure Your Team selection."""
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
        selected, allocation = cls._configured_selection_and_allocation(preference)
        await cls._sync_legacy_agent_fields(preference, selected, allocation)

        return ActiveAgentsResult(
            active_agents=list(selected),
            selected_agents=list(selected),
            allocation=allocation,
        )

    @classmethod
    async def select_agents(cls, account: WalletAccount, selected_agents: list[str]) -> AgentPreference:
        """Compatibility endpoint: updates Configure Your Team selected advisors."""
        valid_ids = cls._valid_advisor_ids()
        invalid = [agent_id for agent_id in selected_agents if agent_id not in valid_ids]
        if invalid:
            raise ValueError(f"Invalid agent IDs: {', '.join(invalid)}")
        if not selected_agents:
            raise ValueError("At least one agent must be selected")
        if len(selected_agents) > 3:
            raise ValueError("You can select at most 3 agents")

        normalized_selected = cls._normalize_selected_agents(selected_agents)
        allocation = AgentPreference.default_advisor_weights(normalized_selected)

        preference, _ = await AgentPreference.objects.aget_or_create(
            account=account,
            defaults={
                "selected_agents": normalized_selected,
                "allocation": allocation,
                "selected_advisors": AgentPreference.default_selected_advisors(),
                "advisor_weights": AgentPreference.default_advisor_weights(),
                "risk_profile": AgentPreference.default_risk_profile(),
            },
        )
        preference.selected_advisors = normalized_selected
        preference.advisor_weights = allocation
        preference.selected_agents = normalized_selected
        preference.allocation = allocation
        await preference.asave(
            update_fields=[
                "selected_advisors",
                "advisor_weights",
                "selected_agents",
                "allocation",
                "updated_at",
            ]
        )
        return preference

    @classmethod
    async def get_allocation(cls, account: WalletAccount) -> dict[str, float]:
        """Get allocation from Configure Your Team selection."""
        result = await cls.get_active_agents_result(account)
        return result.allocation

    @classmethod
    async def update_allocation(cls, account: WalletAccount, allocation: dict[str, float]) -> dict[str, float]:
        """Update Configure Your Team weights and keep legacy fields in sync."""
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

        selected = cls._normalize_selected_agents(list(preference.selected_advisors or []))
        if not selected:
            selected = cls._normalize_selected_agents(AgentPreference.default_selected_advisors())
        if set(allocation.keys()) != set(selected):
            raise ValueError("Allocation must include selected agent IDs only")

        for value in allocation.values():
            if not isinstance(value, (int, float)) or value < 0:
                raise ValueError("Allocation values must be non-negative numbers")

        total = sum(float(value) for value in allocation.values())
        if abs(total - 100.0) > 0.001:
            raise ValueError("Allocation must sum to 100")

        normalized_allocation = cls._normalize_allocation(selected, allocation)
        preference.selected_advisors = list(selected)
        preference.advisor_weights = dict(normalized_allocation)
        preference.selected_agents = list(selected)
        preference.allocation = normalized_allocation
        await preference.asave(
            update_fields=[
                "selected_advisors",
                "advisor_weights",
                "selected_agents",
                "allocation",
                "updated_at",
            ]
        )
        return normalized_allocation

    @classmethod
    async def get_reasoning(cls, account: WalletAccount, asset_id: str) -> AgentReasoning:
        """Get LLM-generated AI agent reasoning for a specific asset."""
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
        selected_agents = cls._normalize_selected_agents(list(preference.selected_advisors or []))
        if not selected_agents:
            selected_agents = cls._normalize_selected_agents(AgentPreference.default_selected_advisors())

        market_snapshot = await FinancialMcpService.list_market_snapshots([asset_id])[0]
        payload = {
            "selected_agents": selected_agents,
            "asset": {
                "asset_id": asset_id,
                "symbol": market_snapshot.symbol,
                "price": str(PricesService.get_price(asset_id)),
                "target_consensus": (
                    str(market_snapshot.target_consensus)
                    if market_snapshot.target_consensus is not None
                    else None
                ),
                "upside_percent": str(market_snapshot.upside_percent),
            },
        }
        result = await LlmAdviceService.complete_json(
            system_prompt=cls._reasoning_system_prompt(),
            user_prompt=json.dumps(payload, ensure_ascii=True),
        )
        reasoning = cls._parse_reasoning(result, selected_agents)
        recommendation = cls._parse_recommendation(result, selected_agents)
        return AgentReasoning(asset_id=asset_id, reasoning=reasoning, recommendation=recommendation)

    @staticmethod
    def _reasoning_system_prompt() -> str:
        return (
            "You are an AI trading committee. "
            "Return strict JSON with keys: reasoning, recommendation. "
            "reasoning must be a list of short strings, one per selected agent. "
            "recommendation must be one of the selected agents."
        )

    @staticmethod
    def _parse_reasoning(payload: dict[str, object], selected_agents: list[str]) -> list[str]:
        raw_reasoning = payload.get("reasoning")
        if not isinstance(raw_reasoning, list):
            raise ValueError("LLM reasoning payload is missing reasoning list")
        reasoning = [str(item).strip() for item in raw_reasoning if str(item).strip()]
        if len(reasoning) < len(selected_agents):
            raise ValueError("LLM reasoning did not return enough items")
        return reasoning

    @staticmethod
    def _parse_recommendation(payload: dict[str, object], selected_agents: list[str]) -> str:
        recommendation = str(payload.get("recommendation", "")).strip()
        if recommendation not in selected_agents:
            raise ValueError("LLM recommendation is invalid")
        return recommendation

    @staticmethod
    def _normalize_selected_agents(selected_agents: list[str]) -> list[str]:
        valid_ids = AIAgentsService._valid_advisor_ids()
        normalized: list[str] = []
        for agent_id in selected_agents:
            if not isinstance(agent_id, str):
                continue
            clean_id = agent_id.strip()
            if clean_id == "":
                continue
            if clean_id not in valid_ids:
                continue
            if clean_id in normalized:
                continue
            normalized.append(clean_id)
            if len(normalized) == 3:
                break
        return normalized

    @staticmethod
    def _valid_advisor_ids() -> set[str]:
        return {advisor.advisor_id for advisor in AdvisorsService.list_advisors()}

    @classmethod
    def _configured_selection_and_allocation(cls, preference: AgentPreference) -> tuple[list[str], dict[str, float]]:
        selected = cls._normalize_selected_agents(list(preference.selected_advisors or []))
        if not selected:
            selected = cls._normalize_selected_agents(list(preference.selected_agents or []))
        if not selected:
            selected = cls._normalize_selected_agents(AgentPreference.default_selected_advisors())
        raw_weights = dict(preference.advisor_weights or {})
        if set(raw_weights.keys()) != set(selected):
            raw_weights = dict(preference.allocation or {})
        allocation = cls._normalize_allocation(selected, raw_weights)
        return selected, allocation

    @classmethod
    async def _sync_legacy_agent_fields(
        cls,
        preference: AgentPreference,
        selected: list[str],
        allocation: dict[str, float],
    ) -> None:
        normalized_selected_agents = cls._normalize_selected_agents(list(preference.selected_agents or []))
        normalized_allocation = cls._normalize_allocation(selected, dict(preference.allocation or {}))
        normalized_advisor_weights = cls._normalize_allocation(selected, dict(preference.advisor_weights or {}))
        if (
            list(preference.selected_advisors or []) == selected
            and normalized_advisor_weights == allocation
            and normalized_selected_agents == selected
            and normalized_allocation == allocation
        ):
            return
        preference.selected_advisors = list(selected)
        preference.advisor_weights = dict(allocation)
        preference.selected_agents = list(selected)
        preference.allocation = dict(allocation)
        await preference.asave(
            update_fields=[
                "selected_advisors",
                "advisor_weights",
                "selected_agents",
                "allocation",
                "updated_at",
            ]
        )

    @staticmethod
    def _normalize_allocation(
        selected_agents: list[str],
        raw_allocation: dict[str, float],
    ) -> dict[str, float]:
        if not selected_agents:
            return {}

        sanitized: dict[str, float] = {}
        for agent_id in selected_agents:
            raw_value = raw_allocation.get(agent_id, 0.0)
            value = float(raw_value) if isinstance(raw_value, (int, float)) else 0.0
            sanitized[agent_id] = max(value, 0.0)

        total = sum(sanitized.values())
        if total <= 0:
            return AgentPreference.default_advisor_weights(selected_agents)

        normalized: dict[str, float] = {}
        for agent_id in selected_agents:
            normalized[agent_id] = round((sanitized[agent_id] / total) * 100.0, 2)

        rounded_total = round(sum(normalized.values()), 2)
        delta = round(100.0 - rounded_total, 2)
        if delta != 0 and selected_agents:
            last_agent = selected_agents[-1]
            normalized[last_agent] = round(normalized[last_agent] + delta, 2)

        return normalized
