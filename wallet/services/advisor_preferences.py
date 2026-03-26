"""Async advisor preferences service for reading and updating advisor preferences."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..constants import DEFAULT_RISK_PROFILE, RISK_PROFILE_IDS
from ..models import AgentPreference, WalletAccount
from .advisors import AdvisorsService

AdvisorWeights = dict[str, float]


@dataclass(frozen=True)
class AdvisorProfile:
    """Persisted advisor and risk selection for an account."""

    selected_advisors: list[str]
    advisor_weights: AdvisorWeights
    risk_profile: str
    onboarding_completed: bool


class AdvisorPreferencesService:
    """Service for reading and updating advisor preferences."""

    @classmethod
    async def get_profile(cls, account: WalletAccount) -> AdvisorProfile:
        """Return the current advisor profile for the account."""
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

        selected_advisors = list(preference.selected_advisors or AgentPreference.default_selected_advisors())
        advisor_weights = cls._normalize_advisor_weights(
            selected_advisors,
            dict(preference.advisor_weights or {}),
        )
        synced_agents = list(selected_advisors)
        synced_allocation = cls._to_agent_allocation(selected_advisors, advisor_weights)
        if list(preference.selected_agents or []) != synced_agents or dict(preference.allocation or {}) != synced_allocation:
            preference.selected_agents = synced_agents
            preference.allocation = synced_allocation
            await preference.asave(update_fields=["selected_agents", "allocation", "updated_at"])
        risk_profile = preference.risk_profile or DEFAULT_RISK_PROFILE
        return AdvisorProfile(
            selected_advisors=selected_advisors,
            advisor_weights=advisor_weights,
            risk_profile=risk_profile,
            onboarding_completed=bool(preference.onboarding_completed),
        )

    @classmethod
    async def update_profile(
        cls,
        account: WalletAccount,
        selected_advisors: list[str],
        advisor_weights: AdvisorWeights | None,
        risk_profile: str,
    ) -> AdvisorProfile:
        """Validate and update advisor profile for an account."""
        cls._validate_selected_advisors(selected_advisors)
        cls._validate_risk_profile(risk_profile)
        validated_weights = cls._validate_and_normalize_advisor_weights(selected_advisors, advisor_weights)

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
        preference.selected_advisors = list(selected_advisors)
        preference.advisor_weights = dict(validated_weights)
        # Keep `/test/agents` in sync with onboarding advisor choices.
        preference.selected_agents = list(selected_advisors)
        preference.allocation = cls._to_agent_allocation(selected_advisors, validated_weights)
        preference.risk_profile = risk_profile
        await preference.asave(
            update_fields=[
                "selected_advisors",
                "advisor_weights",
                "selected_agents",
                "allocation",
                "risk_profile",
                "updated_at",
            ]
        )
        return AdvisorProfile(
            selected_advisors=list(selected_advisors),
            advisor_weights=validated_weights,
            risk_profile=risk_profile,
            onboarding_completed=bool(preference.onboarding_completed),
        )

    @classmethod
    async def mark_onboarding_completed(cls, account: WalletAccount) -> None:
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
        if preference.onboarding_completed:
            return
        preference.onboarding_completed = True
        await preference.asave(update_fields=["onboarding_completed", "updated_at"])

    @classmethod
    async def reset_onboarding(cls, account: WalletAccount) -> AdvisorProfile:
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
        selected_advisors = AgentPreference.default_selected_advisors()
        advisor_weights = AgentPreference.default_advisor_weights(selected_advisors)
        preference.selected_advisors = selected_advisors
        preference.advisor_weights = advisor_weights
        preference.selected_agents = list(selected_advisors)
        preference.allocation = cls._to_agent_allocation(selected_advisors, advisor_weights)
        preference.initial_portfolio = {}
        preference.onboarding_completed = False
        await preference.asave(
            update_fields=[
                "selected_advisors",
                "advisor_weights",
                "selected_agents",
                "allocation",
                "initial_portfolio",
                "onboarding_completed",
                "updated_at",
            ]
        )
        return AdvisorProfile(
            selected_advisors=list(selected_advisors),
            advisor_weights=dict(advisor_weights),
            risk_profile=preference.risk_profile or DEFAULT_RISK_PROFILE,
            onboarding_completed=False,
        )

    @staticmethod
    def _validate_risk_profile(risk_profile: str) -> None:
        if risk_profile not in RISK_PROFILE_IDS:
            raise ValueError(f"Invalid risk_profile. Must be one of: {', '.join(RISK_PROFILE_IDS)}")

    @staticmethod
    def _validate_selected_advisors(selected_advisors: list[str]) -> None:
        if not selected_advisors:
            raise ValueError("selected_advisors must be a non-empty list")
        if len(selected_advisors) > 3:
            raise ValueError("selected_advisors must contain at most 3 advisors")
        if not all(isinstance(advisor_id, str) for advisor_id in selected_advisors):
            raise ValueError("selected_advisors must contain only strings")
        if len(set(selected_advisors)) != len(selected_advisors):
            raise ValueError("selected_advisors must not contain duplicates")

        valid_advisor_ids = {advisor.advisor_id for advisor in AdvisorsService.list_advisors()}
        invalid_ids = [advisor_id for advisor_id in selected_advisors if advisor_id not in valid_advisor_ids]
        if invalid_ids:
            raise ValueError(f"Invalid advisor ids: {', '.join(invalid_ids)}")

    @classmethod
    def _normalize_advisor_weights(
        cls,
        selected_advisors: list[str],
        advisor_weights: AdvisorWeights,
    ) -> AdvisorWeights:
        if not selected_advisors:
            return {}
        if not advisor_weights:
            return AgentPreference.default_advisor_weights(selected_advisors)
        selected_keys = set(selected_advisors)
        if set(advisor_weights.keys()) != selected_keys:
            return AgentPreference.default_advisor_weights(selected_advisors)
        return cls._to_percentage_map(selected_advisors, advisor_weights)

    @classmethod
    def _validate_and_normalize_advisor_weights(
        cls,
        selected_advisors: list[str],
        advisor_weights: AdvisorWeights | None,
    ) -> AdvisorWeights:
        if advisor_weights is None:
            return AgentPreference.default_advisor_weights(selected_advisors)
        if not isinstance(advisor_weights, dict):
            raise ValueError("advisor_weights must be an object")
        selected_keys = set(selected_advisors)
        weight_keys = set(advisor_weights.keys())
        if weight_keys != selected_keys:
            raise ValueError("advisor_weights keys must match selected_advisors")
        normalized = cls._to_percentage_map(selected_advisors, advisor_weights)
        total = sum(Decimal(str(value)) for value in normalized.values())
        if total != Decimal("100.00"):
            raise ValueError("advisor_weights total must equal 100.00")
        return normalized

    @staticmethod
    def _to_percentage_map(
        selected_advisors: list[str],
        advisor_weights: AdvisorWeights,
    ) -> AdvisorWeights:
        normalized: AdvisorWeights = {}
        for advisor_id in selected_advisors:
            raw_value = advisor_weights.get(advisor_id)
            if not isinstance(raw_value, (int, float, str, Decimal)):
                raise ValueError("advisor_weights values must be numeric")
            try:
                parsed = Decimal(str(raw_value)).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                raise ValueError("advisor_weights values must be numeric") from None
            if parsed < Decimal("0.00"):
                raise ValueError("advisor_weights values must be non-negative")
            normalized[advisor_id] = float(parsed)
        return normalized

    @staticmethod
    def _to_agent_allocation(
        selected_advisors: list[str],
        advisor_weights: AdvisorWeights,
    ) -> dict[str, float]:
        return {
            advisor_id: float(advisor_weights.get(advisor_id, 0.0))
            for advisor_id in selected_advisors
        }
